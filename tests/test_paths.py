from pathlib import Path

from janescriber.paths import output_path_for


def test_project_dir_uses_consumer_selected_data_directory(monkeypatch, tmp_path: Path):
    from janescriber.paths import project_dir

    data_dir = tmp_path / "JanesCriberData"
    monkeypatch.setenv("JANESCRIBER_DATA_DIR", str(data_dir))
    assert project_dir() == data_dir.resolve()


def test_output_is_next_to_source(tmp_path: Path):
    source = tmp_path / "my recording.m4a"
    source.write_bytes(b"audio")
    result = output_path_for(source)
    assert result.parent == tmp_path
    assert result.name == "my recording.txt"


def test_existing_output_gets_safe_suffix(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    (tmp_path / "clip.txt").write_text("old", encoding="utf-8")
    assert output_path_for(source).name == "clip (2).txt"


def test_explicit_program_output_directory(tmp_path: Path):
    source = tmp_path / "media" / "clip.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")
    program_dir = tmp_path / "JanesCriber"
    assert output_path_for(source, output_dir=program_dir).parent == program_dir
