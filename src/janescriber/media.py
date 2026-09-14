"""Media validation, probing, and FFmpeg audio extraction."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .cancellation import CancelCheck, check_cancelled, run_cancellable_subprocess


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    size_bytes: int
    duration_seconds: float | None
    has_audio: bool
    has_video: bool


def validate_media_source(source: str | Path) -> Path:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")
    if path.stat().st_size <= 0:
        raise ValueError("The selected media file is empty.")
    return path


def probe_media(source: str | Path, cancel: CancelCheck | None = None) -> MediaInfo:
    """Ask ffprobe for a friendly early validation of the selected media."""
    path = validate_media_source(source)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe was not found. Install the complete FFmpeg package and try again.")
    command = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type",
        "-of", "json",
        str(path),
    ]
    try:
        stdout, stderr = run_cancellable_subprocess(command, cancel)
        payload = json.loads(stdout.decode("utf-8", errors="replace"))
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFprobe could not read this media file: {detail or 'unknown media error'}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFprobe returned an invalid media description.") from exc

    streams = payload.get("streams") or []
    types = {item.get("codec_type") for item in streams if isinstance(item, dict)}
    duration = (payload.get("format") or {}).get("duration")
    try:
        duration_value = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_value = None
    return MediaInfo(
        path=path,
        size_bytes=path.stat().st_size,
        duration_seconds=duration_value if duration_value and duration_value >= 0 else None,
        has_audio="audio" in types,
        has_video="video" in types,
    )


def extract_audio(source: str | Path, destination: str | Path, cancel: CancelCheck | None = None) -> Path:
    """Normalize any FFmpeg-readable media into a Whisper-compatible WAV."""
    source_path = validate_media_source(source)
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found. Install the complete FFmpeg package and try again.")
    check_cancelled(cancel)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source_path), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(target),
    ]
    try:
        run_cancellable_subprocess(command, cancel)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFmpeg could not extract audio: {detail or 'unknown media error'}") from exc
    if not target.is_file() or target.stat().st_size <= 44:
        raise RuntimeError("FFmpeg completed without producing a usable audio stream.")
    return target
