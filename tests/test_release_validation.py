import hashlib
import json
from pathlib import Path

import pytest

from janescriber.release_validation import ReleaseValidationError, validate_release_artifact


def _write_release(tmp_path: Path, *, content: bytes = b"installer") -> tuple[Path, Path, Path]:
    installer = tmp_path / "JanesCriber-1.2.3-Setup.exe"
    installer.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    checksum = installer.with_name(installer.name + ".sha256")
    checksum.write_text(f"{digest}  {installer.name}\n", encoding="ascii")
    manifest = installer.with_name(installer.name + ".json")
    manifest.write_text(
        json.dumps(
            {
                "product": "JanesCriber",
                "version": "1.2.3",
                "installer": installer.name,
                "installerType": "NSIS",
                "ffmpegBundled": True,
                "sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    return installer, manifest, checksum


def test_validate_release_artifact_accepts_matching_manifest_and_checksum(tmp_path: Path):
    installer, manifest, checksum = _write_release(tmp_path)

    result = validate_release_artifact(installer, manifest_path=manifest, checksum_path=checksum)

    assert result["version"] == "1.2.3"
    assert result["sha256"] == hashlib.sha256(installer.read_bytes()).hexdigest()


def test_validate_release_artifact_rejects_checksum_mismatch(tmp_path: Path):
    installer, manifest, checksum = _write_release(tmp_path)
    checksum.write_text(f"{'0' * 64}  {installer.name}\n", encoding="ascii")

    with pytest.raises(ReleaseValidationError, match="Checksum"):
        validate_release_artifact(installer, manifest_path=manifest, checksum_path=checksum)


def test_validate_release_artifact_rejects_manifest_mismatch(tmp_path: Path):
    installer, manifest, checksum = _write_release(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["installer"] = "other.exe"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseValidationError, match="installer"):
        validate_release_artifact(installer, manifest_path=manifest, checksum_path=checksum)
