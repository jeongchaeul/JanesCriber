"""Keep release versions consistent across all JanesCriber launch surfaces."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Callable


class VersionConsistencyError(ValueError):
    """Raised when a project version is missing, malformed, or inconsistent."""


_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VersionConsistencyError(f"Could not read version metadata: {path}") from exc


def _match_version(path: Path, pattern: str) -> str:
    match = re.search(pattern, _read(path), re.MULTILINE | re.DOTALL)
    if not match:
        raise VersionConsistencyError(f"Could not find a version in {path}.")
    version = match.group(1).strip()
    if not _SEMVER.fullmatch(version):
        raise VersionConsistencyError(f"Version in {path} is not stable semantic versioning: {version!r}.")
    return version


def _json_version(path: Path) -> str:
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise VersionConsistencyError(f"Could not parse version metadata: {path}") from exc
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        raise VersionConsistencyError(f"Version in {path} is not stable semantic versioning: {version!r}.")
    return version


def _project_section_version(path: Path, section: str) -> str:
    section_match = re.search(
        rf"(?ms)^\[{re.escape(section)}\]\s*(.*?)(?=^\[|\Z)",
        _read(path),
    )
    if not section_match:
        raise VersionConsistencyError(f"Could not find the [{section}] section in {path}.")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', section_match.group(1), re.MULTILINE)
    if not match:
        raise VersionConsistencyError(f"Could not find a version in [{section}] in {path}.")
    version = match.group(1).strip()
    if not _SEMVER.fullmatch(version):
        raise VersionConsistencyError(f"Version in {path} is not stable semantic versioning: {version!r}.")
    return version


def validate_project_versions(project_root: str | Path, *, expected: str | None = None) -> dict[str, str]:
    """Read and compare Python, package, Tauri, and Cargo version metadata."""
    root = Path(project_root).resolve()
    readers: dict[str, Callable[[], str]] = {
        "python": lambda: _match_version(
            root / "src" / "janescriber" / "__init__.py",
            r'^__version__\s*=\s*["\']([^"\']+)["\']',
        ),
        "pyproject": lambda: _project_section_version(root / "pyproject.toml", "project"),
        "package": lambda: _json_version(root / "desktop-ui" / "package.json"),
        "tauri": lambda: _json_version(root / "desktop-ui" / "src-tauri" / "tauri.conf.json"),
        "cargo": lambda: _project_section_version(root / "desktop-ui" / "src-tauri" / "Cargo.toml", "package"),
    }
    versions = {name: reader() for name, reader in readers.items()}
    unique = set(versions.values())
    if len(unique) != 1:
        details = ", ".join(f"{name}={version}" for name, version in versions.items())
        raise VersionConsistencyError(f"Project version metadata is inconsistent: {details}.")
    actual = next(iter(unique))
    if expected and actual != expected:
        raise VersionConsistencyError(f"Expected project version {expected}, found {actual}.")
    return versions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--version")
    args = parser.parse_args()
    try:
        versions = validate_project_versions(args.root, expected=args.version)
    except VersionConsistencyError as exc:
        parser.error(str(exc))
    print(json.dumps(versions, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
