import queue
import multiprocessing
import shutil
import threading
import time
import wave
from pathlib import Path

from janescriber import pipeline
from janescriber.media import MediaInfo
from janescriber.runtime import configure_runtime


def test_pipeline_cleans_job_and_publishes_atomically(tmp_path: Path, monkeypatch):
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"source media")
    paths = configure_runtime(tmp_path)

    monkeypatch.setattr(
        pipeline,
        "probe_media",
        lambda source, cancel=None: MediaInfo(Path(source).resolve(), 12, 3.0, True, True),
    )

    def fake_extract(source, destination, cancel=None):
        Path(destination).write_bytes(b"wav data")
        return Path(destination)

    monkeypatch.setattr(pipeline, "extract_audio", fake_extract)
    monkeypatch.setattr(
        pipeline,
        "transcribe_audio",
        lambda *args, **kwargs: {
            "text": "hello",
            "segments": [{"start": 0, "end": 1, "text": "hello"}],
            "words": [],
            "language": "en",
        },
    )

    output = pipeline.transcribe_media(source, paths=paths, use_cache=False)

    assert output.exists()
    assert output.parent == paths["transcripts"]
    assert ">hello" in output.read_text(encoding="utf-8")
    assert list(paths["temp"].iterdir()) == []


def test_pipeline_rejects_media_without_audio(tmp_path: Path, monkeypatch):
    source = tmp_path / "silent.mp4"
    source.write_bytes(b"source media")
    paths = configure_runtime(tmp_path)
    monkeypatch.setattr(
        pipeline,
        "probe_media",
        lambda source, cancel=None: MediaInfo(Path(source).resolve(), 12, 3.0, False, True),
    )

    try:
        pipeline.transcribe_media(source, paths=paths)
    except RuntimeError as exc:
        assert "audio stream" in str(exc)
    else:
        raise AssertionError("silent media should be rejected before job creation")


def test_isolated_worker_reports_progress_and_completion(tmp_path: Path, monkeypatch):
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"source media")
    output = tmp_path / "Transcripts" / "meeting.txt"
    paths = configure_runtime(tmp_path)
    events = queue.Queue()

    def fake_transcribe(*args, **kwargs):
        kwargs["progress"](0.5, "Worker is transcribing")
        return output

    monkeypatch.setattr(pipeline, "transcribe_media", fake_transcribe)
    pipeline.run_transcription_job(
        source,
        model_name="tiny",
        language=None,
        paths=paths,
        overwrite=False,
        use_cache=True,
        event_queue=events,
        cancel=threading.Event(),
    )

    assert events.get_nowait() == ("progress", 0.5, "Worker is transcribing")
    assert events.get_nowait() == ("completed", str(output))


def test_isolated_worker_can_spawn_and_reuse_cache(tmp_path: Path):
    if shutil.which("ffprobe") is None:
        return
    source = tmp_path / "meeting.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)

    paths = configure_runtime(tmp_path)
    cached = {"text": "cached", "segments": [{"start": 0, "end": 1, "text": "cached"}], "words": [], "language": "en"}
    pipeline.save(paths["transcript_cache"], pipeline.cache_key(source, "tiny", None), cached)
    events = multiprocessing.get_context("spawn").Queue()
    context = multiprocessing.get_context("spawn")
    cancel = context.Event()
    process = context.Process(
        target=pipeline.run_transcription_job,
        kwargs={
            "source": source,
            "model_name": "tiny",
            "language": None,
            "paths": paths,
            "overwrite": False,
            "use_cache": True,
            "event_queue": events,
            "cancel": cancel,
        },
    )
    process.start()
    received = []
    deadline = time.time() + 20
    try:
        while time.time() < deadline and process.is_alive():
            try:
                received.append(events.get(timeout=0.2))
            except queue.Empty:
                pass
        process.join(timeout=2)
        while True:
            try:
                received.append(events.get_nowait())
            except queue.Empty:
                break
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)

    assert process.exitcode == 0
    assert any(event[0] == "completed" for event in received)
