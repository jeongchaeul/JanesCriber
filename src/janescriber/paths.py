"""Stable project and output path helpers."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .runtime import configure_runtime


def project_dir() -> Path:
    # A packaged consumer install can keep the immutable executable resources
    # separate from the writable data directory selected by the user.
    configured = os.environ.get("JANESCRIBER_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    # Works from source checkout and from a PyInstaller-style executable.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """Return the directory containing bundled read-only application assets."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    configured = os.environ.get("JANESCRIBER_RESOURCE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return project_dir()


def runtime_paths() -> dict[str, Path]:
    return configure_runtime(project_dir())


def output_path_for(
    source: str | Path,
    *,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
    extension: str = "txt",
) -> Path:
    source_path = Path(source).resolve()
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", source_path.stem).strip(" .") or "transcription"
    extension = str(extension).strip().lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]+", extension):
        raise ValueError("Transcript extension must contain letters or numbers only.")
    destination = Path(output_dir).resolve() if output_dir else source_path.parent
    destination.mkdir(parents=True, exist_ok=True)
    candidate = destination / f"{stem}.{extension}"
    if overwrite or not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = destination / f"{stem} ({index}).{extension}"
        if not candidate.exists():
            return candidate
        index += 1


def source_is_supported(path: str | Path) -> bool:
    return Path(path).is_file()
