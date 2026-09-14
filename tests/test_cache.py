from pathlib import Path

from janescriber.cache import load, save


def test_cache_round_trip_is_atomic(tmp_path: Path):
    data = {"text": "hello", "segments": [{"start": 0, "end": 1, "text": "hello"}], "words": []}
    path = save(tmp_path, "abc", data)
    assert path and path.exists()
    assert load(tmp_path, "abc") == data


def test_invalid_cache_is_ignored(tmp_path: Path):
    (tmp_path / "bad.json").write_text('{"segments": "not a list"}', encoding="utf-8")
    assert load(tmp_path, "bad") is None

