import types
import wave
from pathlib import Path

from janescriber import vosk_backend


def test_vosk_result_parser_uses_word_timestamps():
    segment, words = vosk_backend._result_to_parts(
        {
            "text": "hello world",
            "result": [
                {"word": "hello", "start": 0.2, "end": 0.7},
                {"word": "world", "start": 0.8, "end": 1.3},
            ],
        }
    )
    assert segment == {"start": 0.2, "end": 1.3, "text": "hello world"}
    assert len(words) == 2


def test_vosk_audio_transcription_uses_normalized_wav(tmp_path: Path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    with wave.open(str(audio_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 4000)

    class FakeRecognizer:
        def __init__(self, _model, _rate):
            self.calls = 0

        def SetWords(self, _enabled):
            return None

        def AcceptWaveform(self, _data):
            self.calls += 1
            return True

        def Result(self):
            return '{"text":"hello"}'

        def FinalResult(self):
            return '{"text":"world"}'

    fake_vosk = types.SimpleNamespace(
        SetLogLevel=lambda _level: None,
        Model=lambda _path: object(),
        KaldiRecognizer=FakeRecognizer,
    )
    monkeypatch.setitem(__import__("sys").modules, "vosk", fake_vosk)
    monkeypatch.setattr(vosk_backend, "ensure_vosk_model", lambda *args, **kwargs: tmp_path)

    result = vosk_backend.transcribe_vosk_audio(
        audio_path,
        model_id="en-us-small",
        model_cache=tmp_path,
        language="en",
    )

    assert result["text"] == "hello world"
    assert result["language"] == "en"
