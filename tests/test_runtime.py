import os
from pathlib import Path

from janescriber.runtime import configure_runtime


def test_runtime_points_temp_and_model_cache_inside_project(tmp_path: Path):
    paths = configure_runtime(tmp_path)
    assert paths["temp"].parent == tmp_path
    assert paths["transcripts"] == tmp_path / "Transcripts"
    assert paths["transcripts"].is_dir()
    assert paths["model_cache"].is_relative_to(tmp_path)
    assert os.environ["TORCH_HOME"] == str(tmp_path / ".cache" / "torch")


def test_runtime_migrates_legacy_root_transcripts(tmp_path: Path):
    legacy = tmp_path / "meeting.txt"
    legacy.write_text("legacy transcript", encoding="utf-8")

    paths = configure_runtime(tmp_path)

    assert not legacy.exists()
    assert (paths["transcripts"] / "meeting.txt").read_text(encoding="utf-8") == "legacy transcript"
