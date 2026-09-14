from pathlib import Path

import pytest

from janescriber.media import validate_media_source


def test_validate_media_source_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_media_source(tmp_path / "missing.mp4")


def test_validate_media_source_rejects_empty_file(tmp_path: Path):
    source = tmp_path / "empty.mp4"
    source.touch()
    with pytest.raises(ValueError, match="empty"):
        validate_media_source(source)


def test_validate_media_source_resolves_file(tmp_path: Path):
    source = tmp_path / "recording.ogg"
    source.write_bytes(b"media")
    assert validate_media_source(source) == source.resolve()
