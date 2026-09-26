import json
from pathlib import Path

import pytest

from janescriber.versioning import VersionConsistencyError, validate_project_versions


def _write_project(root: Path, versions: dict[str, str]) -> None:
    (root / "src" / "janescriber").mkdir(parents=True)
    (root / "desktop-ui" / "src-tauri").mkdir(parents=True)
    (root / "src" / "janescriber" / "__init__.py").write_text(
        f'__version__ = "{versions["python"]}"\n', encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "janescriber"\nversion = "{versions["pyproject"]}"\n', encoding="utf-8"
    )
    (root / "desktop-ui" / "package.json").write_text(
        json.dumps({"version": versions["package"]}), encoding="utf-8"
    )
    (root / "desktop-ui" / "src-tauri" / "tauri.conf.json").write_text(
        json.dumps({"version": versions["tauri"]}), encoding="utf-8"
    )
    (root / "desktop-ui" / "src-tauri" / "Cargo.toml").write_text(
        f'[package]\nname = "janescriber-studio"\nversion = "{versions["cargo"]}"\n', encoding="utf-8"
    )


def test_validate_project_versions_accepts_matching_metadata(tmp_path: Path):
    versions = {key: "1.2.3" for key in ("python", "pyproject", "package", "tauri", "cargo")}
    _write_project(tmp_path, versions)
    assert validate_project_versions(tmp_path, expected="1.2.3") == versions


def test_validate_project_versions_rejects_drift(tmp_path: Path):
    versions = {key: "1.2.3" for key in ("python", "pyproject", "package", "tauri", "cargo")}
    versions["tauri"] = "1.2.2"
    _write_project(tmp_path, versions)

    with pytest.raises(VersionConsistencyError, match="tauri"):
        validate_project_versions(tmp_path)


def test_repository_versions_are_consistent():
    root = Path(__file__).resolve().parents[1]
    versions = validate_project_versions(root, expected="2.0.0")
    assert set(versions.values()) == {"2.0.0"}
