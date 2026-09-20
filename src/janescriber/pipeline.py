"""Canonical JanesCriber transcription pipeline.

The GUI and CLI both enter here. Validation, media probing, cache lookup,
audio extraction, Whisper execution, and atomic publication are intentionally
kept in one backend contract so the two interfaces cannot drift apart.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

from .cache import cache_key, load, save
from .cancellation import CancelCheck, PipelineAborted, check_cancelled
from .formatting import render_transcript
from .hardware import clear_accelerator_cache, detect_hardware
from .languages import build_multilingual_prompt
from .media import MediaInfo, extract_audio, probe_media, validate_media_source
from .model_manager import ensure_model_downloaded, load_whisper_model
from .paths import output_path_for
from .pipeline_config import TranscriptionConfig, validate_transcription_request
from .vosk_backend import transcribe_vosk_audio
from .wav2vec_backend import transcribe_wav2vec_audio
from .qwen_backend import transcribe_qwen_audio

Progress = Callable[[float, str], None]


class _ProcessOutput:
    """Forward child-process stdout/stderr to the GUI event queue."""

    def __init__(self, event_queue: Any) -> None:
        self.event_queue = event_queue
        self.buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self.buffer += text.replace("\r", "\n")
        parts = self.buffer.split("\n")
        self.buffer = parts.pop()
        for part in parts:
            if part.strip():
                self.event_queue.put(("log", part))
        return len(text)

    def flush(self) -> None:
        if self.buffer.strip():
            self.event_queue.put(("log", self.buffer))
        self.buffer = ""

    def isatty(self) -> bool:
        return False


def run_transcription_job(
    source: str | Path,
    *,
    engine: str = "whisper",
    model_name: str,
    language: str | None,
    output_format: str = "txt",
    paths: dict[str, Path],
    overwrite: bool,
    use_cache: bool,
    event_queue: Any,
    cancel: Any,
) -> None:
    """Run one GUI transcription in an isolated process.

    Keeping Whisper in this process is intentional: once it exits, Windows
    reclaims the CPU model, accelerator staging allocations, and native runtime state
    instead of leaving PyTorch's allocator footprint in the long-lived GUI.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    output = _ProcessOutput(event_queue)
    sys.stdout = output
    sys.stderr = output

    def report(fraction: float, message: str) -> None:
        event_queue.put(("progress", fraction, message))

    try:
        result = transcribe_media(
            source,
            engine=engine,
            model_name=model_name,
            language=language,
            output_format=output_format,
            paths=paths,
            overwrite=overwrite,
            use_cache=use_cache,
            progress=report,
            cancel=cancel,
        )
        event_queue.put(("completed", str(result)))
    except PipelineAborted:
        event_queue.put(("cancelled", ""))
    except BaseException as exc:
        event_queue.put(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        output.flush()
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def _report(progress: Progress | None, fraction: float, message: str) -> None:
    if progress:
        progress(max(0.0, min(1.0, fraction)), message)


def _job_directory(paths: dict[str, Path]) -> Path:
    directory = Path(paths["temp"]).resolve() / f"job_{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def _publish_transcript(destination: Path, content: str) -> Path:
    """Publish text only after the complete UTF-8 file is safely written."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with open(fd, "w", encoding="utf-8", newline="\n", closefd=True) as handle:
            handle.write(content)
            handle.flush()
        Path(temporary_name).replace(destination)
        return destination
    except BaseException:
        try:
            Path(temporary_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _cleanup_job(directory: Path) -> None:
    try:
        shutil.rmtree(directory, ignore_errors=True)
    except OSError:
        pass


def transcribe_audio(
    audio_path: str | Path,
    model_name: str = "turbo",
    model_cache: str | Path | None = None,
    language: str | list[str] | tuple[str, ...] | None = None,
    progress: Progress | None = None,
    cancel: CancelCheck | None = None,
    *,
    engine: str = "whisper",
    vosk_model_cache: str | Path | None = None,
    wav2vec_model_cache: str | Path | None = None,
    qwen_model_cache: str | Path | None = None,
) -> dict[str, Any]:
    """Transcribe one normalized WAV through the selected local ASR engine."""
    check_cancelled(cancel)
    if engine == "vosk":
        if vosk_model_cache is None:
            raise RuntimeError("A project-local Vosk model cache is required.")
        config = TranscriptionConfig(engine="vosk", model_name=model_name, language=language)
        return transcribe_vosk_audio(
            audio_path,
            model_id=config.model_name,
            model_cache=vosk_model_cache,
            language=config.language_arg or "en",
            progress=progress,
            cancel=cancel,
        )
    if engine == "wav2vec2":
        if wav2vec_model_cache is None:
            raise RuntimeError("A project-local Wav2Vec2 model cache is required.")
        config = TranscriptionConfig(engine="wav2vec2", model_name=model_name, language=language)
        hardware = detect_hardware()
        _report(progress, 0.32, f"Preparing Wav2Vec2 {config.model_name} on {hardware['accelerator']}...")
        return transcribe_wav2vec_audio(
            audio_path,
            model_id=config.model_name,
            model_cache=wav2vec_model_cache,
            language=config.language_arg or "en",
            device=str(hardware["device"]),
            progress=progress,
            cancel=cancel,
        )
    if engine == "qwen3-asr":
        if qwen_model_cache is None:
            raise RuntimeError("A project-local Qwen3-ASR model cache is required.")
        config = TranscriptionConfig(engine="qwen3-asr", model_name=model_name, language=language)
        hardware = detect_hardware()
        _report(progress, 0.32, f"Preparing Qwen3-ASR {config.model_name} on {hardware['accelerator']}...")
        return transcribe_qwen_audio(
            audio_path,
            model_id=config.model_name,
            model_cache=qwen_model_cache,
            language=config.language_arg,
            device=str(hardware["device"]),
            progress=progress,
            cancel=cancel,
        )
    if model_cache is None:
        raise RuntimeError("A project-local Whisper model cache is required.")
    audio = validate_media_source(audio_path)
    try:
        import torch
        import whisper
    except ImportError as exc:
        raise RuntimeError("Whisper dependencies are not installed. Run setup.bat or uv sync.") from exc

    hardware = detect_hardware()
    device = str(hardware["device"])
    _report(progress, 0.32, f"Preparing Whisper {model_name} on {hardware['accelerator']}...")
    ensure_model_downloaded(whisper, model_name, model_cache, progress, cancel)

    try:
        model = load_whisper_model(
            whisper, model_name, model_cache, device,
            torch_module=torch, progress=progress, cancel=cancel,
        )
    except PipelineAborted:
        raise
    except Exception as exc:
        if device == "cpu":
            raise RuntimeError(f"Whisper could not load on CPU: {exc}") from exc
        _report(progress, 0.43, f"GPU load was unavailable ({exc}); retrying safely on CPU...")
        try:
            clear_accelerator_cache(torch, device)
        except Exception:
            pass
        device = "cpu"
        model = load_whisper_model(
            whisper, model_name, model_cache, device,
            torch_module=torch, progress=progress, cancel=cancel,
        )

    check_cancelled(cancel)
    language_codes = list(TranscriptionConfig(language=language).language)
    primary_language, initial_prompt = build_multilingual_prompt(language_codes)
    options: dict[str, Any] = {
        "word_timestamps": True,
        "fp16": device == "cuda",
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "compression_ratio_threshold": 2.4,
        "no_speech_threshold": 0.6,
        "verbose": True,
    }
    if primary_language:
        options["language"] = primary_language
        if len(language_codes) > 1:
            _report(progress, 0.46, f"Whisper multilingual mode: primary decoder {primary_language.upper()} | targets {', '.join(language_codes)}")
        else:
            _report(progress, 0.46, f"Whisper language locked to {primary_language.upper()}.")
    else:
        _report(progress, 0.46, "Whisper language: Auto-detect (global multilingual detection).")
    if initial_prompt:
        options["initial_prompt"] = initial_prompt

    _report(progress, 0.55, "Transcribing with word-level timestamps...")
    try:
        # The GUI worker remains responsive while this native call runs. We
        # deliberately do not abandon a second daemon thread on cancellation.
        raw = model.transcribe(str(audio), **options)
    except Exception as exc:
        raise RuntimeError(f"Whisper transcription failed: {exc}") from exc
    check_cancelled(cancel)

    segments = raw.get("segments", []) if isinstance(raw, dict) else []
    words = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        for word in segment.get("words", []) or []:
            if not isinstance(word, dict):
                continue
            try:
                start = float(word.get("start", 0.0))
                end = float(word.get("end", start))
            except (TypeError, ValueError):
                continue
            words.append({
                "word": str(word.get("word", "")).strip(),
                "start": start,
                "end": max(start, end),
            })
    _report(progress, 0.74, f"Whisper finished: {len(segments)} segments, {len(words)} words.")
    return {
        "text": raw.get("text", "") if isinstance(raw, dict) else "",
        "segments": segments,
        "words": words,
        "language": raw.get("language") if isinstance(raw, dict) else None,
    }


def transcribe_media(
    source: str | Path,
    *,
    engine: str = "whisper",
    model_name: str = "turbo",
    language: str | list[str] | tuple[str, ...] | None = None,
    output_format: str = "txt",
    paths: dict[str, Path],
    overwrite: bool = False,
    use_cache: bool = True,
    progress: Progress | None = None,
    cancel: CancelCheck | None = None,
) -> Path:
    """Run one validated, cleaned-up, atomically published transcription job."""
    config = validate_transcription_request(
        engine=engine,
        model_name=model_name,
        language=language,
        overwrite=overwrite,
        use_cache=use_cache,
        output_format=output_format,
    )
    source_path = validate_media_source(source)
    check_cancelled(cancel)
    _report(progress, 0.05, f"Validated input: {source_path.name}")
    media: MediaInfo = probe_media(source_path, cancel)
    if not media.has_audio:
        raise RuntimeError("This media file does not contain an audio stream.")
    _report(progress, 0.12, f"Media ready: {media.path.name} ({media.duration_seconds or 0:.1f}s)")

    output_path = output_path_for(
        source_path,
        output_dir=paths["transcripts"],
        overwrite=config.overwrite,
        extension=config.output_format,
    )
    key = cache_key(source_path, f"{config.engine}:{config.model_name}", config.language_arg)
    job_dir = _job_directory(paths)
    try:
        check_cancelled(cancel)
        data = load(paths["transcript_cache"], key) if config.use_cache else None
        if data is not None:
            _report(progress, 0.60, "Reusing cached transcript; Whisper skipped.")
        else:
            audio_path = job_dir / "audio.wav"
            _report(progress, 0.20, "Extracting a normalized 16 kHz mono audio stream...")
            extract_audio(source_path, audio_path, cancel)
            _report(progress, 0.28, "Audio extraction complete; preparing Whisper...")
            data = transcribe_audio(
                audio_path,
                model_name=config.model_name,
                model_cache=paths["model_cache"],
                vosk_model_cache=paths["vosk_model_cache"],
                wav2vec_model_cache=paths["wav2vec_model_cache"],
                qwen_model_cache=paths["qwen_model_cache"],
                language=config.language_arg,
                progress=progress,
                cancel=cancel,
                engine=config.engine,
            )
            if config.use_cache:
                saved = save(paths["transcript_cache"], key, data)
                if saved is None:
                    _report(progress, 0.76, "Transcript complete; cache could not be written, continuing safely.")

        check_cancelled(cancel)
        _report(progress, 0.85, f"Rendering {config.output_format.upper()} transcript...")
        published = _publish_transcript(
            output_path,
            render_transcript(data, source_path.name, f"{config.engine.title()}: {config.model_name}", config.output_format),
        )
        _report(progress, 1.0, f"Transcript saved in Transcripts: {published.name}")
        return published
    finally:
        _cleanup_job(job_dir)


__all__ = ["extract_audio", "probe_media", "run_transcription_job", "transcribe_audio", "transcribe_media"]
