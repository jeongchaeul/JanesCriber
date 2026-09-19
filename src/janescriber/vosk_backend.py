"""Offline Vosk/Kaldi speech-recognition backend.

Vosk models are downloaded only when the user selects this backend. The
recognizer accepts the normalized 16 kHz mono PCM stream produced by the
JanesCriber media and live-capture pipelines.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
import wave
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cancellation import CancelCheck, PipelineAborted, check_cancelled


_MIN_MODEL_FREE_SPACE = 256 * 1024 * 1024


@dataclass(frozen=True)
class VoskModelSpec:
    """A downloadable Vosk model published by its model maintainer."""

    model_id: str
    label: str
    language: str
    url: str
    license: str


# Small models are intended for desktop and mobile use. The catalog intentionally
# uses the official Vosk model names so users can identify and replace them with
# a compatible community/Kaldi model later if they want to.
VOSK_MODEL_SPECS: dict[str, VoskModelSpec] = {
    "en-us-small": VoskModelSpec(
        "en-us-small", "English (US) · Small", "en",
        "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip", "Apache-2.0",
    ),
    "de-small": VoskModelSpec(
        "de-small", "German · Small", "de",
        "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip", "Apache-2.0",
    ),
    "fr-small": VoskModelSpec(
        "fr-small", "French · Small", "fr",
        "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip", "Apache-2.0",
    ),
    "es-small": VoskModelSpec(
        "es-small", "Spanish · Small", "es",
        "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip", "Apache-2.0",
    ),
    "ru-small": VoskModelSpec(
        "ru-small", "Russian · Small", "ru",
        "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip", "Apache-2.0",
    ),
    "zh-small": VoskModelSpec(
        "zh-small", "Chinese · Small", "zh",
        "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip", "Apache-2.0",
    ),
    "it-small": VoskModelSpec(
        "it-small", "Italian · Small", "it",
        "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip", "Apache-2.0",
    ),
    "pt-small": VoskModelSpec(
        "pt-small", "Portuguese · Small", "pt",
        "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip", "Apache-2.0",
    ),
    "nl-small": VoskModelSpec(
        "nl-small", "Dutch · Small", "nl",
        "https://alphacephei.com/vosk/models/vosk-model-small-nl-0.22.zip", "Apache-2.0",
    ),
    "tr-small": VoskModelSpec(
        "tr-small", "Turkish · Small", "tr",
        "https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip", "Apache-2.0",
    ),
    "ja-small": VoskModelSpec(
        "ja-small", "Japanese · Small", "ja",
        "https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip", "Apache-2.0",
    ),
    "ko-small": VoskModelSpec(
        "ko-small", "Korean · Small", "ko",
        "https://alphacephei.com/vosk/models/vosk-model-small-ko-0.22.zip", "Apache-2.0",
    ),
    "hi-small": VoskModelSpec(
        "hi-small", "Hindi · Small", "hi",
        "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip", "Apache-2.0",
    ),
    "pl-small": VoskModelSpec(
        "pl-small", "Polish · Small", "pl",
        "https://alphacephei.com/vosk/models/vosk-model-small-pl-0.22.zip", "Apache-2.0",
    ),
    "uk-small": VoskModelSpec(
        "uk-small", "Ukrainian · Small", "uk",
        "https://alphacephei.com/vosk/models/vosk-model-small-uk-v3-small.zip", "Apache-2.0",
    ),
    "fa-small": VoskModelSpec(
        "fa-small", "Persian · Small", "fa",
        "https://alphacephei.com/vosk/models/vosk-model-small-fa-0.42.zip", "Apache-2.0",
    ),
    "tl-medium": VoskModelSpec(
        "tl-medium", "Filipino / Tagalog · Medium", "tl",
        "https://alphacephei.com/vosk/models/vosk-model-tl-ph-generic-0.6.zip", "CC-BY-NC-SA-4.0",
    ),
    "vi-small": VoskModelSpec(
        "vi-small", "Vietnamese · Small", "vi",
        "https://alphacephei.com/vosk/models/vosk-model-small-vn-0.4.zip", "Apache-2.0",
    ),
    "te-small": VoskModelSpec(
        "te-small", "Telugu · Small", "te",
        "https://alphacephei.com/vosk/models/vosk-model-small-te-0.42.zip", "Apache-2.0",
    ),
}

VOSK_MODEL_LABELS = {key: spec.label for key, spec in VOSK_MODEL_SPECS.items()}
VOSK_LANGUAGE_TO_MODEL = {spec.language: key for key, spec in VOSK_MODEL_SPECS.items()}


def model_spec(model_id: str) -> VoskModelSpec:
    try:
        return VOSK_MODEL_SPECS[model_id]
    except KeyError as exc:
        choices = ", ".join(VOSK_MODEL_SPECS)
        raise RuntimeError(f"Unknown Vosk model '{model_id}'. Choose from: {choices}") from exc


def default_model_for_language(language: str | None) -> str:
    return VOSK_LANGUAGE_TO_MODEL.get(str(language or "en").split(",")[0].strip().lower(), "en-us-small")


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        candidate = (destination / member.filename).resolve()
        if not candidate.is_relative_to(root):
            raise RuntimeError("The Vosk model archive contains an unsafe path.")
    archive.extractall(destination)


def _model_payload(path: Path) -> Path:
    directories = [item for item in path.iterdir() if item.is_dir()]
    if len(directories) == 1 and (directories[0] / "am").is_dir():
        return directories[0]
    return path


def _valid_model(path: Path) -> bool:
    return path.is_dir() and (path / "am" / "final.mdl").is_file() and (path / "conf").is_dir()


def ensure_vosk_model(
    model_id: str,
    model_cache: str | Path,
    progress=None,
    cancel: CancelCheck | None = None,
) -> Path:
    """Download and atomically unpack one Vosk model into the project cache."""
    spec = model_spec(model_id)
    cache_dir = Path(model_cache).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / spec.model_id
    marker = target / ".janescriber-ready"
    if marker.is_file() and _valid_model(target):
        if progress:
            progress(0.35, f"Vosk model ready: {spec.label}")
        return target

    archive_path = cache_dir / f".{spec.model_id}.zip"
    staging = Path(tempfile.mkdtemp(prefix=f".{spec.model_id}-", dir=cache_dir))
    try:
        if progress:
            progress(0.25, f"Downloading Vosk model: {spec.label}…")
        request = urllib.request.Request(spec.url, headers={"User-Agent": "JanesCriber/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response, archive_path.open("wb") as handle:
            total_header = response.headers.get("Content-Length")
            total = int(total_header) if total_header and total_header.isdigit() else 0
            free_bytes = shutil.disk_usage(cache_dir).free
            required_bytes = max(_MIN_MODEL_FREE_SPACE, total + _MIN_MODEL_FREE_SPACE)
            if free_bytes < required_bytes:
                raise RuntimeError(
                    f"Not enough free space on {cache_dir.drive or cache_dir.anchor}. "
                    f"Need about {required_bytes / 1073741824:.1f} GB for the Vosk model download."
                )
            received = 0
            while True:
                check_cancelled(cancel)
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if progress:
                    detail = f"{received / 1048576:.0f} MB"
                    if total:
                        detail += f" / {total / 1048576:.0f} MB"
                    progress(0.25 + min(0.10, 0.10 * received / total) if total else 0.25, f"Downloading Vosk model: {detail}")

        check_cancelled(cancel)
        if progress:
            progress(0.36, f"Unpacking Vosk model: {spec.label}…")
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("The downloaded Vosk model archive is corrupt.")
            _safe_extract(archive, staging)
        payload = _model_payload(staging)
        if not _valid_model(payload):
            raise RuntimeError("The downloaded archive is not a valid Vosk model.")
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        payload.rename(target)
        marker.write_text(f"{spec.model_id}\n", encoding="utf-8")
        (target / "MODEL_LICENSE.txt").write_text(
            f"JanesCriber Vosk model: {spec.label}\n"
            f"License: {spec.license}\n"
            f"Source: {spec.url}\n",
            encoding="utf-8",
        )
        if progress:
            progress(0.40, f"Vosk model ready: {spec.label}")
        return target
    except PipelineAborted:
        raise
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, RuntimeError) as exc:
        raise RuntimeError(f"Vosk model download failed: {exc}") from exc
    finally:
        archive_path.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


def _result_to_parts(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    words: list[dict[str, Any]] = []
    for item in payload.get("result", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start", 0.0))
            end = max(start, float(item.get("end", start)))
        except (TypeError, ValueError):
            continue
        word = str(item.get("word", "")).strip()
        if word:
            words.append({"word": word, "start": start, "end": end})
    text = " ".join(str(payload.get("text", "")).split())
    if not text and words:
        text = " ".join(item["word"] for item in words)
    if not text:
        return None, words
    start = words[0]["start"] if words else 0.0
    end = words[-1]["end"] if words else start
    return {"start": start, "end": max(start, end), "text": text}, words


def transcribe_vosk_audio(
    audio_path: str | Path,
    *,
    model_id: str,
    model_cache: str | Path,
    language: str,
    progress=None,
    cancel: CancelCheck | None = None,
) -> dict[str, Any]:
    """Transcribe normalized WAV audio with a local Vosk/Kaldi recognizer."""
    try:
        import vosk
    except ImportError as exc:
        raise RuntimeError("Vosk is not installed. Run setup.bat again to add the Vosk/Kaldi backend.") from exc

    model_path = ensure_vosk_model(model_id, model_cache, progress, cancel)
    spec = model_spec(model_id)
    try:
        vosk.SetLogLevel(-1)
    except AttributeError:
        pass
    model = vosk.Model(str(model_path))
    segments: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    with wave.open(str(audio_path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
            raise RuntimeError("Vosk requires normalized 16 kHz mono 16-bit audio.")
        recognizer = vosk.KaldiRecognizer(model, audio.getframerate())
        recognizer.SetWords(True)
        total_frames = max(1, audio.getnframes())
        processed = 0
        while True:
            check_cancelled(cancel)
            data = audio.readframes(4000)
            if not data:
                break
            processed += len(data) // 2
            if recognizer.AcceptWaveform(data):
                payload = json.loads(recognizer.Result() or "{}")
                segment, segment_words = _result_to_parts(payload)
                if segment:
                    segments.append(segment)
                    words.extend(segment_words)
            if progress:
                progress(0.42 + min(0.30, 0.30 * processed / total_frames), f"Vosk transcribing: {processed / 16000:.1f}s / {total_frames / 16000:.1f}s")
        final_payload = json.loads(recognizer.FinalResult() or "{}")
        segment, segment_words = _result_to_parts(final_payload)
        if segment:
            segments.append(segment)
            words.extend(segment_words)
    return {
        "text": " ".join(segment["text"] for segment in segments),
        "segments": segments,
        "words": words,
        "language": spec.language or language,
    }


__all__ = [
    "VOSK_LANGUAGE_TO_MODEL",
    "VOSK_MODEL_LABELS",
    "VOSK_MODEL_SPECS",
    "default_model_for_language",
    "ensure_vosk_model",
    "model_spec",
    "transcribe_vosk_audio",
]
