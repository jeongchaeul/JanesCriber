"""Validated configuration shared by the GUI, CLI, and transcription engine."""

from __future__ import annotations

from dataclasses import dataclass

from .languages import normalize_language_codes
from .vosk_backend import VOSK_MODEL_SPECS, default_model_for_language
from .wav2vec_backend import WAV2VEC2_MODEL_SPECS
from .qwen_backend import QWEN_MODEL_SPECS, QWEN_SUPPORTED_CODES


SUPPORTED_ENGINES = ("whisper", "vosk", "wav2vec2", "qwen3-asr")
SUPPORTED_MODELS = ("turbo", "large-v3", "medium", "small", "base", "tiny")
SUPPORTED_OUTPUT_FORMATS = ("txt", "srt", "vtt", "json")


@dataclass(frozen=True)
class TranscriptionConfig:
    """Normalized options accepted by one transcription job."""

    engine: str = "whisper"
    model_name: str = "turbo"
    language: tuple[str, ...] = ()
    overwrite: bool = False
    use_cache: bool = True
    output_format: str = "txt"

    def __post_init__(self) -> None:
        engine = str(self.engine).strip().lower()
        if engine not in SUPPORTED_ENGINES:
            raise ValueError(f"Unsupported ASR engine '{self.engine}'. Choose from: {', '.join(SUPPORTED_ENGINES)}")
        object.__setattr__(self, "engine", engine)

        model = str(self.model_name).strip().lower()
        languages = tuple(normalize_language_codes(self.language))
        if engine == "whisper":
            if model not in SUPPORTED_MODELS:
                raise ValueError(f"Unsupported Whisper model '{self.model_name}'. Choose from: {', '.join(SUPPORTED_MODELS)}")
        elif engine == "vosk":
            if model in {"", "auto", "turbo"}:
                model = default_model_for_language(languages[0] if languages else "en")
            if model not in VOSK_MODEL_SPECS:
                raise ValueError(f"Unsupported Vosk model '{self.model_name}'. Choose from: {', '.join(VOSK_MODEL_SPECS)}")
            if len(languages) > 1:
                raise ValueError("Vosk / Kaldi uses one language model at a time. Choose one spoken language.")
            if len(languages) == 1 and VOSK_MODEL_SPECS[model].language != languages[0]:
                raise ValueError(
                    f"Vosk model '{model}' is for {VOSK_MODEL_SPECS[model].language}, "
                    f"but the selected language is {languages[0]}. Choose a matching model."
                )
            if not languages:
                languages = (VOSK_MODEL_SPECS[model].language,)
        elif engine == "wav2vec2":
            if model in {"", "auto", "turbo"}:
                model = "wav2vec2-base-960h"
            if model not in WAV2VEC2_MODEL_SPECS:
                raise ValueError(f"Unsupported Wav2Vec2 model '{self.model_name}'.")
            if languages and languages != ("en",):
                raise ValueError("Wav2Vec2 currently supports English only. Choose English or use Whisper/Vosk.")
            languages = ("en",)
        else:
            if model in {"", "auto", "turbo"}:
                model = "qwen3-asr-0.6b"
            if model not in QWEN_MODEL_SPECS:
                raise ValueError(f"Unsupported Qwen3-ASR model '{self.model_name}'. Choose from: {', '.join(QWEN_MODEL_SPECS)}")
            unsupported = [code for code in languages if code not in QWEN_SUPPORTED_CODES]
            if unsupported:
                raise ValueError(f"Qwen3-ASR does not support language code(s): {', '.join(unsupported)}. Use Whisper for these languages.")
        object.__setattr__(self, "model_name", model)

        if len(languages) > 8:
            raise ValueError("Choose no more than eight spoken languages.")
        object.__setattr__(self, "language", languages)
        object.__setattr__(self, "overwrite", bool(self.overwrite))
        object.__setattr__(self, "use_cache", bool(self.use_cache))
        output_format = str(self.output_format).strip().lower().lstrip(".")
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"Unsupported transcript format '{self.output_format}'. "
                f"Choose from: {', '.join(SUPPORTED_OUTPUT_FORMATS)}"
            )
        object.__setattr__(self, "output_format", output_format)

    @property
    def language_arg(self) -> str | None:
        return ",".join(self.language) or None


def validate_transcription_request(
    engine: str = "whisper",
    model_name: str = "turbo",
    language: str | list[str] | tuple[str, ...] | None = None,
    *,
    overwrite: bool = False,
    use_cache: bool = True,
    output_format: str = "txt",
) -> TranscriptionConfig:
    """Validate all user-controlled options before creating runtime state."""
    return TranscriptionConfig(
        engine=engine,
        model_name=model_name,
        language=tuple(normalize_language_codes(language)),
        overwrite=overwrite,
        use_cache=use_cache,
        output_format=output_format,
    )
