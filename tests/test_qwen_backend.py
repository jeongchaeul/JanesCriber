import types
import wave
from pathlib import Path

from janescriber import qwen_backend


def test_qwen_language_mapping_includes_filipino():
    assert qwen_backend.qwen_language_name("tl") == "Filipino"
    assert qwen_backend.qwen_language_name("en,tl") is None


def test_qwen_file_transcription_uses_bounded_chunks(tmp_path: Path, monkeypatch):
    source = tmp_path / "long.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * (31 * 16000))

    calls = []

    class FakeModel:
        def transcribe(self, **kwargs):
            samples, rate = kwargs["audio"]
            calls.append((len(samples), rate, kwargs["language"]))
            return [types.SimpleNamespace(text=f"chunk {len(calls)}", language="English")]

    monkeypatch.setattr(qwen_backend, "load_qwen_asr_model", lambda *args, **kwargs: (FakeModel(), "cpu"))
    result = qwen_backend.transcribe_qwen_audio(
        source,
        model_id="qwen3-asr-0.6b",
        model_cache=tmp_path / "cache",
        language="en",
    )

    assert calls == [(480000, 16000, "English"), (16000, 16000, "English")]
    assert result["language"] == "English"
    assert result["segments"] == [
        {"start": 0.0, "end": 30.0, "text": "chunk 1"},
        {"start": 30.0, "end": 31.0, "text": "chunk 2"},
    ]
