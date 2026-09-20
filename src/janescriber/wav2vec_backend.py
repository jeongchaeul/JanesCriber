"""Local Wav2Vec2 ASR backend using the existing Torch runtime.

This backend is intentionally small and opt-in.  The model is downloaded from
Hugging Face only when selected, stored under the project cache, and moved to
the best accelerator exposed by the installed Torch runtime.
"""

from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cancellation import CancelCheck, check_cancelled
from .hardware import resolve_accelerator_device


@dataclass(frozen=True)
class Wav2VecModelSpec:
    model_id: str
    label: str
    repository: str
    language: str
    license: str


WAV2VEC2_MODEL_SPECS: dict[str, Wav2VecModelSpec] = {
    "wav2vec2-base-960h": Wav2VecModelSpec(
        "wav2vec2-base-960h",
        "Wav2Vec2 · English · GPU capable",
        "facebook/wav2vec2-base-960h",
        "en",
        "Apache-2.0",
    ),
}
WAV2VEC2_MODEL_LABELS = {key: spec.label for key, spec in WAV2VEC2_MODEL_SPECS.items()}
_FILE_CHUNK_SECONDS = 30.0


def model_spec(model_id: str) -> Wav2VecModelSpec:
    try:
        return WAV2VEC2_MODEL_SPECS[model_id]
    except KeyError as exc:
        raise RuntimeError(f"Unknown Wav2Vec2 model '{model_id}'.") from exc


def _load_session(model_id: str, model_cache: str | Path, device: str, progress, cancel: CancelCheck | None):
    spec = model_spec(model_id)
    check_cancelled(cancel)
    try:
        import torch
        from transformers import AutoModelForCTC, AutoProcessor
    except ImportError as exc:
        raise RuntimeError(
            "Wav2Vec2 needs the Transformers package. Run setup.bat again to install the optional GPU backend."
        ) from exc
    cache_dir = Path(model_cache).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(0.30, f"Loading Wav2Vec2 model: {spec.label}…")
    processor = AutoProcessor.from_pretrained(spec.repository, cache_dir=str(cache_dir))
    check_cancelled(cancel)
    model = AutoModelForCTC.from_pretrained(spec.repository, cache_dir=str(cache_dir))
    check_cancelled(cancel)
    selected_device = device if device in {"cuda", "xpu", "mps", "dml"} else "cpu"
    if progress:
        progress(0.42, f"Moving Wav2Vec2 into {selected_device.upper()} memory…")
    runtime_device: Any = selected_device
    try:
        runtime_device = resolve_accelerator_device(selected_device, torch)
        model = model.to(runtime_device)
    except Exception as exc:
        if selected_device == "cpu":
            raise
        if progress:
            progress(0.44, f"{selected_device.upper()} model load was unavailable ({exc}); retrying Wav2Vec2 on CPU…")
        selected_device = "cpu"
        runtime_device = "cpu"
        model = model.to("cpu")
    model.eval()
    if progress:
        progress(0.48, f"Wav2Vec2 ready on {selected_device.upper()}.")
    return processor, model, selected_device, runtime_device, torch


def _segments_from_offsets(text: str, offsets: list[dict[str, Any]], frame_count: int, duration: float, offset: float):
    if not offsets or frame_count <= 0:
        clean = " ".join(text.split())
        return ([{"start": offset, "end": offset + max(0.0, duration), "text": clean}] if clean else []), []
    scale = duration / frame_count
    words: list[dict[str, Any]] = []
    current: list[str] = []
    current_start: float | None = None
    current_end = 0.0

    def commit() -> None:
        nonlocal current, current_start, current_end
        if not current or current_start is None:
            current = []
            current_start = None
            current_end = 0.0
            return
        word = "".join(current).strip()
        if word:
            words.append({"word": word, "start": offset + current_start, "end": offset + current_end})
        current = []
        current_start = None
        current_end = 0.0

    for item in offsets:
        char = str(item.get("char", ""))
        try:
            start = float(item.get("start_offset", 0)) * scale
            end = float(item.get("end_offset", item.get("start_offset", 0))) * scale
        except (TypeError, ValueError):
            continue
        if char in {" ", "|"}:
            commit()
            continue
        if current_start is None:
            current_start = start
        current.append(char)
        current_end = max(current_end, end)
    commit()
    if not words:
        clean = " ".join(text.split())
        return ([{"start": offset, "end": offset + max(0.0, duration), "text": clean}] if clean else []), []

    segments: list[dict[str, Any]] = []
    group: list[dict[str, Any]] = []
    for word in words:
        group.append(word)
        if len(group) >= 12 or word["word"].endswith(('.', '?', '!')):
            segments.append({"start": group[0]["start"], "end": group[-1]["end"], "text": " ".join(item["word"] for item in group)})
            group = []
    if group:
        segments.append({"start": group[0]["start"], "end": group[-1]["end"], "text": " ".join(item["word"] for item in group)})
    return segments, words


class Wav2Vec2Session:
    """Reusable model session for file and rolling live recognition."""

    def __init__(self, processor: Any, model: Any, device: str, runtime_device: Any, torch_module: Any) -> None:
        self.processor = processor
        self.model = model
        self.device = device
        self.runtime_device = runtime_device
        self.torch = torch_module

    def transcribe_samples(self, samples: Any, *, sample_rate: int = 16000, offset: float = 0.0) -> dict[str, Any]:
        import numpy as np

        values = np.asarray(samples, dtype=np.float32).reshape(-1)
        duration = len(values) / sample_rate if len(values) else 0.0
        if not len(values):
            return {"text": "", "segments": [], "words": [], "language": "en"}
        inputs = self.processor(values, sampling_rate=sample_rate, return_tensors="pt", padding=True)
        inputs = {key: value.to(self.runtime_device) for key, value in inputs.items() if hasattr(value, "to")}
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits
        predicted = self.torch.argmax(logits, dim=-1)
        try:
            decoded = self.processor.batch_decode(predicted, output_char_offsets=True)
            text = decoded["text"][0] if isinstance(decoded, dict) else decoded[0]
            offsets = decoded.get("char_offsets", [[]])[0] if isinstance(decoded, dict) else []
        except (TypeError, ValueError, AttributeError):
            text = self.processor.batch_decode(predicted)[0]
            offsets = []
        text = " ".join(str(text).split())
        segments, words = _segments_from_offsets(text, offsets, int(logits.shape[1]), duration, offset)
        return {"text": text, "segments": segments, "words": words, "language": "en"}


def load_wav2vec2_session(model_id: str, model_cache: str | Path, device: str, progress=None, cancel=None) -> Wav2Vec2Session:
    processor, model, selected_device, runtime_device, torch = _load_session(model_id, model_cache, device, progress, cancel)
    return Wav2Vec2Session(processor, model, selected_device, runtime_device, torch)


def transcribe_wav2vec_audio(
    audio_path: str | Path,
    *,
    model_id: str,
    model_cache: str | Path,
    language: str,
    device: str = "cpu",
    progress=None,
    cancel: CancelCheck | None = None,
) -> dict[str, Any]:
    """Transcribe a normalized 16 kHz mono WAV with local Wav2Vec2."""
    session = load_wav2vec2_session(model_id, model_cache, device, progress, cancel)
    segments: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    sample_count = 0
    with wave.open(str(audio_path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
            raise RuntimeError("Wav2Vec2 requires normalized 16 kHz mono 16-bit audio.")
        total_frames = audio.getnframes()
        chunk_frames = max(1, round(_FILE_CHUNK_SECONDS * audio.getframerate()))
        import numpy as np

        while sample_count < total_frames:
            check_cancelled(cancel)
            frames = audio.readframes(min(chunk_frames, total_frames - sample_count))
            if not frames:
                break
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            result = session.transcribe_samples(
                samples,
                sample_rate=audio.getframerate(),
                offset=sample_count / audio.getframerate(),
            )
            segments.extend(result.get("segments", []))
            words.extend(result.get("words", []))
            sample_count += len(samples)
            if progress:
                fraction = sample_count / max(1, total_frames)
                progress(0.50 + min(0.24, 0.24 * fraction), f"Wav2Vec2 transcribing: {sample_count / audio.getframerate():.1f}s / {total_frames / audio.getframerate():.1f}s")

    result = {
        "text": " ".join(str(segment.get("text", "")).strip() for segment in segments if segment.get("text")),
        "segments": segments,
        "words": words,
        "language": language or "en",
    }
    if progress:
        progress(0.74, f"Wav2Vec2 finished: {len(result['segments'])} segments.")
    if not result["segments"] and sample_count:
        result["segments"] = [{"start": 0.0, "end": sample_count / 16000.0, "text": "No speech detected."}]
    return result


__all__ = [
    "WAV2VEC2_MODEL_LABELS",
    "WAV2VEC2_MODEL_SPECS",
    "Wav2Vec2Session",
    "load_wav2vec2_session",
    "model_spec",
    "transcribe_wav2vec_audio",
]
