from pathlib import Path

import pytest

from janescriber.launcher import (
    FRONTEND_MAIN,
    FRONTEND_PYTHON,
    find_main_ui,
    read_frontend_preference,
    write_frontend_preference,
)


def test_frontend_preference_is_project_local_and_round_trips(tmp_path: Path):
    preference_path = write_frontend_preference(FRONTEND_PYTHON, tmp_path)

    assert preference_path == tmp_path / "frontend.preference"
    assert preference_path.read_text(encoding="utf-8").strip() == FRONTEND_PYTHON
    assert read_frontend_preference(tmp_path) == FRONTEND_PYTHON


def test_invalid_frontend_preference_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        write_frontend_preference("unknown", tmp_path)


def test_main_ui_is_discovered_beside_the_project(tmp_path: Path):
    main_ui = tmp_path / "JanesCriberStudio.exe"
    main_ui.write_bytes(b"native ui")

    assert find_main_ui(tmp_path) == main_ui
    assert read_frontend_preference(tmp_path) == FRONTEND_MAIN
