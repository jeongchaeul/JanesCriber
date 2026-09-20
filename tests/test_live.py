from pathlib import Path
import queue
import sys
import types

import numpy as np
import pytest

from janescriber.live import (
    CaptureSource,
    LiveSegment,
    LiveTranscriptionConfig,
    LiveTranscriber,
    _format_application_label,
)
from janescriber.runtime import configure_runtime


def test_live_config_defaults_to_fast_model():
    config = LiveTranscriptionConfig()
    assert config.engine == "whisper"
    assert config.model_name == "tiny"
    assert config.window_seconds > config.hop_seconds


@pytest.mark.parametrize("model", ["unknown", "", "large"])
def test_live_config_rejects_unsupported_model(model):
    with pytest.raises(ValueError):
        LiveTranscriptionConfig(model_name=model)


def test_live_transcript_renders_timestamped_blocks(tmp_path: Path):
    paths = configure_runtime(tmp_path)
    live = LiveTranscriber(paths, LiveTranscriptionConfig())
    live._started_at = "2026-09-11 12-00-00"
    live._segments = [LiveSegment(0.66, 3.64, "Hey there")]
    rendered = live._render()
    assert "[00:00:00.660 --> 00:00:03.640]" in rendered
    assert ">Hey there" in rendered


def test_live_output_path_stays_in_transcripts_folder(tmp_path: Path):
    paths = configure_runtime(tmp_path)
    live = LiveTranscriber(paths, LiveTranscriptionConfig())
    path = live._next_output_path("2026-09-11 12-00-00")
    assert path.parent == paths["transcripts"]


def test_live_capture_reports_audio_dropped_when_queue_is_saturated(tmp_path: Path):
    paths = configure_runtime(tmp_path)
    statuses: list[str] = []
    live = LiveTranscriber(paths, LiveTranscriptionConfig(), on_status=statuses.append)
    live._audio_queue = queue.Queue(maxsize=1)
    live._audio_queue.put(np.zeros(4, dtype=np.float32))

    live._enqueue_array(np, np.ones(4, dtype=np.float32), 16000)

    assert live._dropped_audio_chunks == 1
    assert statuses == [
        "Live audio buffer is full; dropped 1 audio chunk. Use a smaller live model or shorten the session."
    ]
    assert np.array_equal(live._audio_queue.get_nowait(), np.ones(4, dtype=np.float32))


def test_live_capture_source_is_preserved_in_rendered_notes(tmp_path: Path):
    paths = configure_runtime(tmp_path)
    source = CaptureSource("application", "Discord.exe — PID 4321", identifier="Discord.exe", pid=4321)
    live = LiveTranscriber(paths, LiveTranscriptionConfig(), capture_source=source)
    live._started_at = "2026-09-11 12-00-00"
    assert "Source: Discord.exe — PID 4321" in live._render()


def test_live_source_defaults_to_microphone_for_legacy_device_name(tmp_path: Path):
    paths = configure_runtime(tmp_path)
    live = LiveTranscriber(paths, LiveTranscriptionConfig(), device_name="USB microphone")
    assert live.capture_source.kind == "microphone"
    assert live.capture_source.identifier == "USB microphone"


def test_application_picker_uses_friendly_window_labels_without_pid():
    label = _format_application_label("Discord.exe", "lounge-1 | arcelia")
    assert label == "Discord — lounge-1 | arcelia"
    assert "PID" not in label


def test_application_capture_uses_installed_proctap_api(tmp_path: Path, monkeypatch):
    paths = configure_runtime(tmp_path)
    calls = []

    class FakeProcessAudioCapture:
        def __init__(self, pid, on_data):
            calls.append(("init", pid, on_data))

        def start(self):
            calls.append(("start",))

    monkeypatch.setitem(sys.modules, "proctap", types.SimpleNamespace(ProcessAudioCapture=FakeProcessAudioCapture))
    live = LiveTranscriber(
        paths,
        LiveTranscriptionConfig(),
        capture_source=CaptureSource("application", "Discord", pid=4321),
    )

    live._start_application_capture()

    assert calls[0][0:2] == ("init", 4321)
    assert calls[0][2] == live._application_audio_callback
    assert calls[1] == ("start",)


def test_live_vosk_config_selects_a_single_language_model():
    config = LiveTranscriptionConfig(engine="vosk", model_name="auto", language=("tl",))
    assert config.model_name == "tl-medium"
    assert config.language == ("tl",)


def test_live_vosk_config_rejects_multiple_languages():
    with pytest.raises(ValueError, match="one language model"):
        LiveTranscriptionConfig(engine="vosk", model_name="en-us-small", language=("en", "tl"))


def test_live_vosk_config_rejects_a_mismatched_model_language():
    with pytest.raises(ValueError, match="matching model"):
        LiveTranscriptionConfig(engine="vosk", model_name="en-us-small", language=("tl",))


def test_live_wav2vec_config_is_english_and_gpu_capable():
    config = LiveTranscriptionConfig(engine="wav2vec2", model_name="auto", language=("en",))
    assert config.model_name == "wav2vec2-base-960h"
    assert config.language == ("en",)


def test_live_wav2vec_config_rejects_non_english():
    with pytest.raises(ValueError, match="English only"):
        LiveTranscriptionConfig(engine="wav2vec2", model_name="auto", language=("tl",))


def test_live_qwen_config_is_rejected_until_streaming_backend_is_available():
    with pytest.raises(ValueError, match="file transcription only"):
        LiveTranscriptionConfig(engine="qwen3-asr", model_name="auto", language=("tl",))
