from pathlib import Path

import pytest

from janescriber.library import discover_transcripts, is_managed_transcript, read_transcript


def test_discover_transcripts_is_newest_first(tmp_path: Path):
    older = tmp_path / "older.txt"
    newer = tmp_path / "newer.txt"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")
    assert [item.path.name for item in discover_transcripts(tmp_path)] == ["newer.txt", "older.txt"]


def test_library_actions_are_scoped_to_program_folder(tmp_path: Path):
    transcript = tmp_path / "one.txt"
    transcript.write_text("hello", encoding="utf-8")
    outside = tmp_path / "media" / "two.txt"
    outside.parent.mkdir()
    outside.write_text("no", encoding="utf-8")
    assert is_managed_transcript(transcript, tmp_path)
    assert not is_managed_transcript(outside, tmp_path)
    assert read_transcript(transcript, tmp_path) == "hello"
    with pytest.raises(ValueError):
        read_transcript(outside, tmp_path)

