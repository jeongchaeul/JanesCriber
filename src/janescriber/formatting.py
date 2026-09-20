"""Human-readable timestamped transcript rendering."""

from __future__ import annotations

import math
import json
from typing import Any


def timestamp(seconds: float) -> str:
    total_ms = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _segments(data: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for segment in data.get("segments") or []:
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
        start_value = max(0.0, start_value)
        records.append({"start": start_value, "end": max(start_value, end_value), "text": text})
    return records


def render_text(data: dict[str, Any], source_name: str, model: str) -> str:
    segments = _segments(data)
    lines = [
        "JANESCRIBER TRANSCRIPT",
        f"Source: {source_name}",
        f"Model: {model}",
        f"Language: {data.get('language') or 'Auto-detected'}",
        "",
    ]
    for segment in segments:
        text = segment["text"]
        start_value = segment["start"]
        end_value = segment["end"]
        start = timestamp(max(0.0, start_value))
        end = timestamp(max(start_value, end_value))
        lines.extend([f"[{start} --> {end}]", "", f">{text}", ""])
    if len(lines) == 5:
        lines.extend(["[00:00:00.000 --> 00:00:00.000]", "", ">No speech detected."])
    return "\n".join(lines) + "\n"


def _subtitle_timestamp(seconds: float) -> str:
    return timestamp(seconds).replace(".", ",")


def render_srt(data: dict[str, Any], _source_name: str, _model: str) -> str:
    """Render standard SubRip subtitles from the normalized segment contract."""
    blocks: list[str] = []
    for index, segment in enumerate(_segments(data), start=1):
        blocks.append(
            f"{index}\n{_subtitle_timestamp(segment['start'])} --> "
            f"{_subtitle_timestamp(segment['end'])}\n{segment['text']}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(data: dict[str, Any], _source_name: str, _model: str) -> str:
    """Render WebVTT subtitles from the normalized segment contract."""
    blocks: list[str] = []
    for segment in _segments(data):
        blocks.append(
            f"{timestamp(segment['start'])} --> {timestamp(segment['end'])}\n{segment['text']}"
        )
    body = "\n\n".join(blocks)
    return "WEBVTT\n\n" + body + ("\n" if body else "")


def render_json(data: dict[str, Any], source_name: str, model: str) -> str:
    """Render a stable, metadata-preserving JSON transcript for integrations."""
    payload = {
        "format": "janescriber.transcript.v1",
        "source": source_name,
        "model": model,
        "language": data.get("language"),
        "text": str(data.get("text") or "").strip(),
        "segments": _segments(data),
        "words": data.get("words") or [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_transcript(data: dict[str, Any], source_name: str, model: str, output_format: str = "txt") -> str:
    """Render a transcript in one of the supported local export formats."""
    normalized = str(output_format).strip().lower().lstrip(".")
    renderers = {"txt": render_text, "srt": render_srt, "vtt": render_vtt, "json": render_json}
    try:
        renderer = renderers[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported transcript format: {output_format}") from exc
    return renderer(data, source_name, model)
