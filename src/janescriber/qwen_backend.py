"""Optional Qwen3-ASR backend for stronger multilingual transcription.

Qwen3-ASR is kept opt-in because its official Python package brings a larger
dependency tree than the built-in engines. Model weights and the Hugging Face
cache still live under JanesCriber's project-local cache on D:.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cancellation import CancelCheck, check_cancelled
from .hardware import clear_accelerator_cache


@dataclass(frozen=True)
class QwenModelSpec:
    model_id: str
    label: str
    repository: str
    license: str


QWEN_MODEL_SPECS: dict[str, QwenModelSpec] = {
    "qwen3-asr-0.6b": QwenModelSpec(
        "qwen3-asr-0.6b",
        "Qwen3-ASR 0.6B · multilingual · GPU capable",
        "Qwen/Qwen3-ASR-0.6B",
        "Apache-2.0",
    ),
    "qwen3-asr-1.7b": QwenModelSpec(
        "qwen3-asr-1.7b",
        "Qwen3-ASR 1.7B · highest accuracy · GPU recommended",
        "Qwen/Qwen3-ASR-1.7B",
        "Apache-2.0",
    ),
}
QWEN_MODEL_LABELS = {key: spec.label for key, spec in QWEN_MODEL_SPECS.items()}

QWEN_LANGUAGE_NAMES = {
    "zh": "Chinese", "en": "English", "yue": "Cantonese", "ar": "Arabic",
    "de": "German", "fr": "French", "es": "Spanish", "pt": "Portuguese",
    "id": "Indonesian", "it": "Italian", "ko": "Korean", "ru": "Russian",
    "th": "Thai", "vi": "Vietnamese", "ja": "Japanese", "tr": "Turkish",
    "hi": "Hindi", "ms": "Malay", "nl": "Dutch", "sv": "Swedish",
    "da": "Danish", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
    "fil": "Filipino", "tl": "Filipino", "fa": "Persian", "el": "Greek",
    "hu": "Hungarian", "mk": "Macedonian", "ro": "Romanian",
}
QWEN_SUPPORTED_CODES = frozenset(QWEN_LANGUAGE_NAMES)
_FILE_CHUNK_SECONDS = 30.0


def model_spec(model_id: str) -> QwenModelSpec:
    try:
        return QWEN_MODEL_SPECS[model_id]
    except KeyError as exc:
        raise RuntimeError(f"Unknown Qwen3-ASR model '{model_id}'.") from exc


def qwen_language_name(language: str | None) -> str | None:
    code = str(language or "").strip().lower()
    if not code or "," in code:
        return None
    try:
        return QWEN_LANGUAGE_NAMES[code]
    except KeyError as exc:
        supported = ", ".join(sorted(set(QWEN_LANGUAGE_NAMES.values())))
        raise RuntimeError(f"Qwen3-ASR does not support language code '{code}'. Supported languages: {supported}.") from exc


def load_qwen_asr_model(model_id: str, model_cache: str | Path, device: str, progress=None, cancel: CancelCheck | None = None):
    """Load Qwen3-ASR on the requested accelerator, falling back to CPU."""
    spec = model_spec(model_id)
    check_cancelled(cancel)
    try:
        import torch
        from qwen_asr import Qwen3ASRModel
    except ImportError as exc:
        raise RuntimeError(
            "Qwen3-ASR is not installed. Run install.ps1 -WithQwen to add the optional local model pack."
        ) from exc

    cache_dir = Path(model_cache).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    requested = device if device in {"cuda", "xpu", "mps"} else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        requested = "cpu"
    xpu_backend = getattr(torch, "xpu", None)
    if requested == "xpu" and (xpu_backend is None or not xpu_backend.is_available()):
        requested = "cpu"
    mps_backend = getattr(torch.backends, "mps", None)
    if requested == "mps" and (mps_backend is None or not mps_backend.is_available()):
        requested = "cpu"
    if progress:
        progress(0.34, f"Loading {spec.label} on {requested.upper()} (first use downloads into D: project cache)…")

    def _load(selected: str):
        kwargs: dict[str, Any] = {
            "cache_dir": str(cache_dir),
            "dtype": torch.float16 if selected in {"cuda", "xpu", "mps"} else torch.float32,
            "max_inference_batch_size": 1,
            "max_new_tokens": 512,
        }
        if selected in {"cuda", "xpu", "mps"}:
            kwargs["device_map"] = f"{selected}:0" if selected in {"cuda", "xpu"} else selected
        return Qwen3ASRModel.from_pretrained(spec.repository, **kwargs)

    try:
        model = _load(requested)
    except Exception as exc:
        if requested == "cpu":
            raise
        clear_accelerator_cache(torch, requested)
        if progress:
            progress(0.40, f"{requested.upper()} model load was unavailable ({exc}); retrying Qwen3-ASR on CPU…")
        requested = "cpu"
        model = _load(requested)
    check_cancelled(cancel)
    if progress:
        progress(0.48, f"Qwen3-ASR ready on {requested.upper()}.")
    return model, requested


def _result_text(result: Any) -> str:
    return " ".join(str(getattr(result, "text", "") or "").split())


def _result_language(result: Any) -> str | None:
    value = getattr(result, "language", None)
    return str(value).strip() if value else None


def transcribe_qwen_audio(
    audio_path: str | Path,
    *,
    model_id: str,
    model_cache: str | Path,
    language: str | None,
    device: str = "cpu",
    progress=None,
    cancel: CancelCheck | None = None,
) -> dict[str, Any]:
    """Transcribe normalized audio in bounded chunks through Qwen3-ASR.

    The official forced aligner is an additional model and does not cover all
    Qwen ASR languages. JanesCriber therefore emits honest chunk-boundary
    timestamps here rather than pretending its text has word-level timing.
    Whisper remains the recommended engine when exact word timestamps matter.
    """
    model, _ = load_qwen_asr_model(model_id, model_cache, device, progress, cancel)
    # Qwen accepts one forced language per audio item. For a multilingual
    # selection, leave it on automatic detection instead of forcing only the
    # first selected language.
    forced_language = qwen_language_name(language) if language and "," not in language else None
    segments: list[dict[str, Any]] = []
    detected_languages: list[str] = []

    with wave.open(str(audio_path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
            raise RuntimeError("Qwen3-ASR requires normalized 16 kHz mono 16-bit audio.")
        total_frames = audio.getnframes()
        chunk_frames = max(1, round(_FILE_CHUNK_SECONDS * audio.getframerate()))
        import numpy as np

        processed = 0
        while processed < total_frames:
            check_cancelled(cancel)
            frames = audio.readframes(min(chunk_frames, total_frames - processed))
            if not frames:
                break
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            offset = processed / audio.getframerate()
            duration = len(samples) / audio.getframerate()
            result = model.transcribe(
                audio=(samples, audio.getframerate()),
                language=forced_language,
                return_time_stamps=False,
            )[0]
            text = _result_text(result)
            detected = _result_language(result)
            if detected and detected not in detected_languages:
                detected_languages.append(detected)
            if text:
                segments.append({"start": offset, "end": offset + duration, "text": text})
            processed += len(samples)
            if progress:
                fraction = processed / max(1, total_frames)
                progress(0.50 + min(0.24, 0.24 * fraction), f"Qwen3-ASR transcribing: {processed / 16000:.1f}s / {total_frames / 16000:.1f}s")

    detected_language = ", ".join(detected_languages) if detected_languages else (forced_language or language or None)
    data = {
        "text": " ".join(segment["text"] for segment in segments),
        "segments": segments,
        "words": [],
        "language": detected_language,
    }
    if progress:
        progress(0.74, f"Qwen3-ASR finished: {len(segments)} timestamp blocks (chunk timing).")
    return data


__all__ = [
    "QWEN_LANGUAGE_NAMES", "QWEN_MODEL_LABELS", "QWEN_MODEL_SPECS",
    "QWEN_SUPPORTED_CODES", "load_qwen_asr_model", "model_spec",
    "qwen_language_name", "transcribe_qwen_audio",
]
