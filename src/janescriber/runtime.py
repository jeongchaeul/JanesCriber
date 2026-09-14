"""Application-local runtime paths.

Runtime configuration happens before importing Torch or Whisper so model and
temporary files stay beside the program instead of silently filling C:.
"""

from __future__ import annotations

import os
from pathlib import Path


def configure_runtime(base_dir: str | Path, *, create_directories: bool = True) -> dict[str, Path]:
    base = Path(base_dir).resolve()
    paths = {
        "base": base,
        "transcripts": base / "Transcripts",
        "temp": base / "temp",
        "cache": base / ".cache",
        "model_cache": base / ".cache" / "whisper",
        "vosk_model_cache": base / ".cache" / "vosk",
        "wav2vec_model_cache": base / ".cache" / "wav2vec2",
        "transcript_cache": base / ".cache" / "transcripts",
        "logs": base / ".cache" / "logs",
    }
    if create_directories:
        for path in paths.values():
            if path != base:
                path.mkdir(parents=True, exist_ok=True)
        _migrate_root_transcripts(base, paths["transcripts"])

    # FFmpeg, Whisper, Hugging Face helpers, Torch and Python's tempfile all
    # respect these variables. Keeping them app-local avoids C: bloat.
    os.environ["TEMP"] = str(paths["temp"])
    os.environ["TMP"] = str(paths["temp"])
    os.environ["TMPDIR"] = str(paths["temp"])
    os.environ["TORCH_HOME"] = str(paths["cache"] / "torch")
    os.environ["XDG_CACHE_HOME"] = str(paths["cache"])
    os.environ["HF_HOME"] = str(paths["cache"] / "huggingface")
    os.environ["TRITON_CACHE_DIR"] = str(paths["cache"] / "triton")
    bundled_ffmpeg = base / "ffmpeg"
    if bundled_ffmpeg.is_dir():
        os.environ["PATH"] = str(bundled_ffmpeg) + os.pathsep + os.environ.get("PATH", "")
    return paths


def _migrate_root_transcripts(base: Path, transcripts: Path) -> None:
    """Move legacy root-level text outputs into the managed folder safely."""
    try:
        legacy_files = [path for path in base.glob("*.txt") if path.is_file() and not path.name.startswith(".")]
    except OSError:
        return
    for source in legacy_files:
        destination = transcripts / source.name
        index = 2
        while destination.exists():
            destination = transcripts / f"{source.stem} ({index}){source.suffix}"
            index += 1
        try:
            source.replace(destination)
        except OSError:
            # A locked or concurrently changed legacy file stays untouched.
            continue
