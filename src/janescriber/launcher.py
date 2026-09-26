"""Shared interface preference and relaunch helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .paths import project_dir

FRONTEND_MAIN = "tauri"
FRONTEND_PYTHON = "python"
VALID_FRONTENDS = frozenset({FRONTEND_MAIN, FRONTEND_PYTHON})
PREFERENCE_NAME = "frontend.preference"


def _root(base_dir: str | Path | None = None) -> Path:
    return Path(base_dir or project_dir()).resolve()


def preference_path(base_dir: str | Path | None = None) -> Path:
    return _root(base_dir) / PREFERENCE_NAME


def read_frontend_preference(base_dir: str | Path | None = None) -> str:
    try:
        value = preference_path(base_dir).read_text(encoding="utf-8").strip().casefold()
    except OSError:
        return FRONTEND_MAIN
    return value if value in VALID_FRONTENDS else FRONTEND_MAIN


def write_frontend_preference(preference: str = FRONTEND_MAIN, base_dir: str | Path | None = None) -> Path:
    value = preference.strip().casefold()
    if value not in VALID_FRONTENDS:
        raise ValueError(f"Unsupported frontend preference: {preference}")
    path = preference_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    return path


def find_main_ui(base_dir: str | Path | None = None) -> Path | None:
    root = _root(base_dir)
    candidates = (
        root / "JanesCriberStudio.exe",
        root / "janescriber-studio.exe",
        root / "JanesCriber Studio.exe",
        root / "desktop-ui" / "src-tauri" / "target" / "release" / "janescriber-studio.exe",
        root / "janescriber-studio",
        root / "JanesCriberStudio",
        root / "JanesCriber Studio",
        root / "desktop-ui" / "src-tauri" / "target" / "release" / "janescriber-studio",
        root / "JanesCriber Studio.app" / "Contents" / "MacOS" / "JanesCriber Studio",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def relaunch_command(base_dir: str | Path | None = None) -> list[str]:
    main_ui = find_main_ui(base_dir)
    if main_ui is not None:
        return [str(main_ui)]
    root = _root(base_dir)
    universal_launcher = root / "JanesCriber.exe"
    if universal_launcher.is_file():
        return [str(universal_launcher)]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "janescriber"]


def launch_main_ui(base_dir: str | Path | None = None) -> subprocess.Popen[bytes]:
    main_ui = find_main_ui(base_dir)
    if main_ui is None:
        raise FileNotFoundError("JanesCriber Studio was not found. Please build or run JanesCriberStudio.")
    root = _root(base_dir)
    environment = os.environ.copy()
    environment["JANESCRIBER_DATA_DIR"] = str(root)
    launch_kwargs: dict[str, object] = {
        "cwd": str(main_ui.parent),
        "env": environment,
        "close_fds": os.name != "nt",
    }
    return subprocess.Popen([str(main_ui)], **launch_kwargs)
