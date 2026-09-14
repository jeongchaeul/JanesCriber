"""Stable project and output path helpers."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .runtime import configure_runtime


def project_dir() -> Path:
    # Works from source checkout and from a PyInstaller-style executable.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """Return the directory containing bundled read-only application assets."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return project_dir()


def runtime_paths() -> dict[str, Path]:
    return configure_runtime(project_dir())


def output_path_for(source: str | Path, *, output_dir: str | Path | None = None, overwrite: bool = False) -> Path:
    source_path = Path(source).resolve()
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", source_path.stem).strip(" .") or "transcription"
    destination = Path(output_dir).resolve() if output_dir else source_path.parent
    destination.mkdir(parents=True, exist_ok=True)
    candidate = destination / f"{stem}.txt"
    if overwrite or not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = destination / f"{stem} ({index}).txt"
        if not candidate.exists():
            return candidate
        index += 1


def source_is_supported(path: str | Path) -> bool:
    return Path(path).is_file()
