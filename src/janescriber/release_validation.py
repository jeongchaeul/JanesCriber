"""Validate a JanesCriber consumer release artifact before publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


class ReleaseValidationError(ValueError):
    """Raised when a release artifact cannot be trusted as self-consistent."""


_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_CHECKSUM_PATTERN = re.compile(r"^([0-9a-fA-F]{64})\s+(.+?)\s*$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseValidationError(f"Could not read release manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ReleaseValidationError("Release manifest must contain a JSON object.")
    return payload


def _read_checksum(path: Path, installer_name: str) -> str:
    try:
        raw = path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise ReleaseValidationError(f"Could not read checksum file: {path}") from exc
    match = _CHECKSUM_PATTERN.fullmatch(raw)
    if not match:
        raise ReleaseValidationError("Checksum file must contain a SHA-256 digest and installer filename.")
    digest, recorded_name = match.groups()
    if Path(recorded_name).name != installer_name:
        raise ReleaseValidationError(
            f"Checksum file names {recorded_name!r}, but the installer is {installer_name!r}."
        )
    return digest.lower()


def validate_release_artifact(
    installer_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
    checksum_path: str | Path | None = None,
    expected_version: str | None = None,
) -> dict[str, Any]:
    """Validate an installer, manifest, and checksum as one release unit."""
    installer = Path(installer_path).resolve()
    if not installer.is_file() or installer.stat().st_size <= 0:
        raise ReleaseValidationError(f"Installer does not exist or is empty: {installer}")
    if not installer.name.lower().endswith("-setup.exe"):
        raise ReleaseValidationError("Consumer installer must use the '*-Setup.exe' filename contract.")

    manifest = Path(manifest_path).resolve() if manifest_path else installer.with_name(installer.name + ".json")
    checksum = Path(checksum_path).resolve() if checksum_path else installer.with_name(installer.name + ".sha256")
    payload = _read_json(manifest)
    digest = _sha256_file(installer)
    recorded_digest = _read_checksum(checksum, installer.name)

    product = payload.get("product")
    version = payload.get("version")
    if product != "JanesCriber":
        raise ReleaseValidationError("Release manifest product must be JanesCriber.")
    if not isinstance(version, str) or not _VERSION_PATTERN.fullmatch(version):
        raise ReleaseValidationError("Release manifest version must be a stable semantic version.")
    if expected_version and version != expected_version:
        raise ReleaseValidationError(f"Expected release version {expected_version}, found {version}.")
    if payload.get("installer") != installer.name:
        raise ReleaseValidationError("Release manifest installer name does not match the artifact.")
    if payload.get("ffmpegBundled") is not True:
        raise ReleaseValidationError("Release manifest must confirm that FFmpeg is bundled.")
    if str(payload.get("sha256", "")).lower() != digest:
        raise ReleaseValidationError("Release manifest SHA-256 does not match the installer.")
    if recorded_digest != digest:
        raise ReleaseValidationError("Checksum file SHA-256 does not match the installer.")

    return {
        "installer": str(installer),
        "manifest": str(manifest),
        "checksum": str(checksum),
        "product": product,
        "version": version,
        "sha256": digest,
        "bytes": installer.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--checksum", type=Path)
    parser.add_argument("--version")
    args = parser.parse_args()
    try:
        result = validate_release_artifact(
            args.installer,
            manifest_path=args.manifest,
            checksum_path=args.checksum,
            expected_version=args.version,
        )
    except ReleaseValidationError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
