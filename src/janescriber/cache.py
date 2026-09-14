"""Validated, atomic transcript caching."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


def cache_key(source: str | Path, model: str, language: str | None) -> str:
    path = Path(source).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(f"{path.name}|{stat.st_size}|{stat.st_mtime_ns}|{model}|{language or 'auto'}".encode("utf-8"))
    # A small content sample prevents stale reuse when a file is replaced while
    # retaining the same name, size, or coarse filesystem timestamp.
    with path.open("rb") as handle:
        digest.update(handle.read(64 * 1024))
    return digest.hexdigest()[:32]


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_word(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start, end = value.get("start"), value.get("end")
    return (
        isinstance(value.get("word"), str)
        and _valid_number(start)
        and _valid_number(end)
        and end >= start
    )


def _valid_segment(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start, end = value.get("start"), value.get("end")
    return (
        isinstance(value.get("text"), str)
        and _valid_number(start)
        and _valid_number(end)
        and end >= start
    )


def _valid(data: Any) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return False
    segments = data.get("segments")
    words = data.get("words", [])
    if not isinstance(segments, list) or not isinstance(words, list):
        return False
    return all(_valid_segment(item) for item in segments) and all(_valid_word(item) for item in words)


def load(cache_dir: str | Path, key: str) -> dict[str, Any] | None:
    path = Path(cache_dir) / f"{key}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if _valid(data) else None
    except (OSError, ValueError, TypeError):
        return None


def save(cache_dir: str | Path, key: str, data: dict[str, Any]) -> Path | None:
    if not _valid(data):
        return None
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{key}.json"
    fd, temp_name = tempfile.mkstemp(prefix=".transcript-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_name, target)
        return target
    except OSError:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        return None
