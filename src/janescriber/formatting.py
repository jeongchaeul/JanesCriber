"""Human-readable timestamped transcript rendering."""

from __future__ import annotations

import math
from typing import Any


def timestamp(seconds: float) -> str:
    total_ms = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def render_text(data: dict[str, Any], source_name: str, model: str) -> str:
    segments = data.get("segments") or []
    lines = [
        "JANESCRIBER TRANSCRIPT",
        f"Source: {source_name}",
        f"Model: {model}",
        f"Language: {data.get('language') or 'Auto-detected'}",
        "",
    ]
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = " ".join(str(segment.get("text", "")).split())
        if not text:
            continue
        try:
            start_value = float(segment.get("start", 0.0))
            end_value = float(segment.get("end", start_value))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(start_value) or not math.isfinite(end_value):
            continue
        start = timestamp(max(0.0, start_value))
        end = timestamp(max(start_value, end_value))
        lines.extend([f"[{start} --> {end}]", "", f">{text}", ""])
    if len(lines) == 5:
        lines.extend(["[00:00:00.000 --> 00:00:00.000]", "", ">No speech detected."])
    return "\n".join(lines) + "\n"
