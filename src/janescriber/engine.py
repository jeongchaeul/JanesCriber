"""Whisper + FFmpeg transcription engine."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .cache import cache_key, load, save
from .hardware import clear_accelerator_cache, detect_hardware, resolve_accelerator_device
from .languages import build_multilingual_prompt, normalize_language_codes
from .paths import output_path_for

# Canonical implementations live in pipeline.py. The import is intentionally
# at the end of this legacy-compatible module so existing GUI/CLI imports keep
# working while callers converge on the structured pipeline.

Progress = Callable[[float, str], None]


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel and cancel.is_set():
        raise RuntimeError("Transcription cancelled")


def extract_audio(source: str | Path, destination: str | Path, cancel: threading.Event | None = None) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and confirm ffmpeg -version works.")
    _check_cancel(cancel)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr)
        raise RuntimeError(f"FFmpeg could not read this media file: {message.strip() or exc}") from exc
    return Path(destination)


def _ensure_model_downloaded(
    whisper_module: Any,
    model_name: str,
    model_cache: str | Path,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    """Download a Whisper model with GUI-visible progress and atomic caching."""
    model_url = getattr(whisper_module, "_MODELS", {}).get(model_name)
    if not model_url:
        raise RuntimeError(f"Unknown Whisper model: {model_name}")
    cache_dir = Path(model_cache)
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urllib.parse.urlparse(model_url).path).name
    target = cache_dir / filename

    # Whisper's built-in downloader considers any existing file reusable. A
    # cancelled Windows download can leave a zero-byte file, so reject tiny
    # artifacts before handing the path to torch.load().
    try:
        if target.exists() and target.stat().st_size < 1024 * 1024:
            target.unlink()
    except OSError as exc:
        raise RuntimeError(f"The cached Whisper model is unusable and could not be replaced: {exc}") from exc
    if target.exists():
        if progress:
            progress(0.35, f"Whisper {model_name} model already downloaded; loading it...")
        return target

    if progress:
        progress(0.30, f"Downloading Whisper {model_name} model to the D: project cache...")
    temp_name: str | None = None
    received = 0
    try:
        request = urllib.request.Request(model_url, headers={"User-Agent": "JanesCriber/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            total_header = response.headers.get("Content-Length")
            total = int(total_header) if total_header and total_header.isdigit() else 0
            digest = hashlib.sha256()
            fd, temp_name = tempfile.mkstemp(prefix=f".{filename}.", suffix=".download", dir=cache_dir)
            with os.fdopen(fd, "wb") as handle:
                while True:
                    _check_cancel(cancel)
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if progress:
                        if total:
                            fraction = received / total
                            progress(0.30 + min(0.10, 0.10 * fraction), f"Downloading Whisper {model_name}: {received / 1048576:.0f} / {total / 1048576:.0f} MB")
                        else:
                            progress(0.30, f"Downloading Whisper {model_name}: {received / 1048576:.0f} MB")
            if total and received != total:
                raise RuntimeError(f"download ended early ({received} of {total} bytes received)")
            expected = urllib.parse.urlparse(model_url).path.rstrip("/").split("/")[-2]
            if len(expected) == 64 and digest.hexdigest() != expected:
                raise RuntimeError("download checksum did not match the Whisper model")
        os.replace(temp_name, target)
        temp_name = None
        return target
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Whisper model download failed. Check internet access and try again. ({exc})") from exc
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise RuntimeError(f"Whisper model download failed: {exc}") from exc
        raise RuntimeError(f"Whisper model download failed: {exc}") from exc
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def transcribe_audio(
    audio_path: str | Path,
    model_name: str = "turbo",
    model_cache: str | Path | None = None,
    language: str | list[str] | None = None,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    _check_cancel(cancel)
    try:
        import torch
        import whisper
    except ImportError as exc:
        raise RuntimeError("Whisper dependencies are not installed. Run uv sync.") from exc

    hw = detect_hardware()
    device = str(hw["device"])
    fp16 = device == "cuda"
    if not model_cache:
        raise RuntimeError("A project-local Whisper model cache is required.")
    _ensure_model_downloaded(whisper, model_name, model_cache, progress, cancel)
    if progress:
        progress(0.40, f"Loading Whisper {model_name} on {device.upper()} ({hw['accelerator']})...")
    model_result: dict[str, Any] = {}
    model_errors: list[BaseException] = []

    def load_worker() -> None:
        try:
            # Constructing Whisper with torch.load(map_location="cuda") can
            # trigger a native access violation on some Windows/PyTorch/GPU
            # combinations. Build the exact same model safely on CPU first,
            # then transfer the fully constructed weights to the accelerator.
            if progress and device != "cpu":
                progress(0.40, f"Constructing Whisper {model_name} safely on CPU before {device.upper()} transfer...")
            model = whisper.load_model(model_name, device="cpu", download_root=str(model_cache))
            if device != "cpu":
                clear_accelerator_cache(torch, device)
                if progress:
                    progress(0.42, f"Moving Whisper {model_name} into {device.upper()} memory...")
                model = model.to(resolve_accelerator_device(device, torch))
            model_result["model"] = model
        except BaseException as exc:
            model_errors.append(exc)

    model_thread = threading.Thread(target=load_worker, daemon=True, name="JanesCriberWhisperModelLoad")
    model_thread.start()
    load_started = time.monotonic()
    last_load_status = load_started
    while model_thread.is_alive():
        model_thread.join(timeout=0.25)
        _check_cancel(cancel)
        now = time.monotonic()
        if progress and now - last_load_status >= 3.0:
            progress(0.40, f"Loading Whisper {model_name} into {device.upper()} memory... ({now - load_started:.0f}s elapsed)")
            last_load_status = now
    if model_errors:
        raise RuntimeError(f"Whisper could not load the cached model: {model_errors[0]}") from model_errors[0]
    model = model_result["model"]
    _check_cancel(cancel)
    options: dict[str, Any] = {
        "word_timestamps": True,
        "fp16": fp16,
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "compression_ratio_threshold": 2.4,
        "no_speech_threshold": 0.6,
        # Match JaneClipper: Whisper's own segment/progress stream is routed
        # into the desktop Console Logs view by the GUI worker.
        "verbose": True,
    }
    language_codes = normalize_language_codes(language)
    primary_language, initial_prompt = build_multilingual_prompt(language_codes)
    if primary_language:
        options["language"] = primary_language
        if len(language_codes) > 1:
            if progress:
                progress(0.46, f"Whisper multilingual mode: primary decoder {primary_language.upper()} | targets {', '.join(language_codes)}")
        elif progress:
            progress(0.46, f"Whisper language locked to {primary_language.upper()}.")
    elif progress:
        progress(0.46, "Whisper language: Auto-detect (global multilingual detection).")
    if initial_prompt:
        options["initial_prompt"] = initial_prompt
    if progress:
        progress(0.55, "Transcribing with word-level timestamps...")

    result: dict[str, Any] = {}
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            result["data"] = model.transcribe(str(audio_path), **options)
        except BaseException as exc:  # preserve the original Whisper error
            errors.append(exc)

    thread = threading.Thread(target=worker, daemon=True, name="JanesCriberWhisper")
    thread.start()
    transcription_started = time.monotonic()
    last_transcription_status = transcription_started
    while thread.is_alive():
        thread.join(timeout=0.25)
        _check_cancel(cancel)
        now = time.monotonic()
        if progress and now - last_transcription_status >= 5.0:
            progress(0.56, f"Whisper is processing the audio... ({now - transcription_started:.0f}s elapsed)")
            last_transcription_status = now
    if errors:
        raise RuntimeError(str(errors[0])) from errors[0]
    raw = result.get("data", {})
    words = []
    for segment in raw.get("segments", []):
        for word in segment.get("words", []):
            words.append({"word": str(word.get("word", "")).strip(), "start": float(word.get("start", 0)), "end": float(word.get("end", 0))})
    if progress:
        progress(0.74, f"Whisper finished: {len(raw.get('segments', []))} segments, {len(words)} words.")
    return {"text": raw.get("text", ""), "segments": raw.get("segments", []), "words": words, "language": raw.get("language")}


def transcribe_media(
    source: str | Path,
    *,
    model_name: str = "turbo",
    language: str | list[str] | None = None,
    paths: dict[str, Path],
    overwrite: bool = False,
    use_cache: bool = True,
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Media file not found: {source_path}")
    output_path = output_path_for(source_path, output_dir=paths["transcripts"], overwrite=overwrite)
    language_key = ",".join(normalize_language_codes(language)) or None
    key = cache_key(source_path, model_name, language_key)
    data = load(paths["transcript_cache"], key) if use_cache else None
    if data:
        if progress:
            progress(0.60, "Reusing cached transcript; Whisper skipped.")
    else:
        work_dir = paths["temp"] / f"job_{key[:12]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        audio_path = work_dir / "audio.wav"
        if progress:
            progress(0.20, "Extracting a normalized 16 kHz mono audio stream...")
        extract_audio(source_path, audio_path, cancel)
        if progress:
            progress(0.28, "Audio extraction complete; preparing Whisper...")
        data = transcribe_audio(audio_path, model_name, paths["model_cache"], language, progress, cancel)
        if use_cache:
            save(paths["transcript_cache"], key, data)

    if progress:
        progress(0.85, "Rendering timestamped text transcript...")
    output_path.write_text(render_text(data, source_path.name, model_name), encoding="utf-8")
    if progress:
            progress(1.0, f"Transcript saved in Transcripts: {output_path.name}")
    return output_path


# Backward-compatible exports. New entrypoints use the structured pipeline,
# while older integrations importing janescriber.engine keep the same API.
from .pipeline import (  # noqa: E402  (intentional compatibility boundary)
    extract_audio,
    probe_media,
    transcribe_audio,
    transcribe_media,
)


from .formatting import render_text
