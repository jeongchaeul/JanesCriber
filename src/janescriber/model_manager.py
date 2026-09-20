"""Whisper model acquisition and safe device loading."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .cancellation import CancelCheck, PipelineAborted, check_cancelled
from .hardware import clear_accelerator_cache, resolve_accelerator_device


_MIN_MODEL_FREE_SPACE = 512 * 1024 * 1024
_MODEL_DOWNLOAD_ATTEMPTS = 3


def _sha256_file(path: Path, cancel: CancelCheck | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            check_cancelled(cancel)
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _expected_model_hash(model_url: str) -> str | None:
    value = urllib.parse.urlparse(model_url).path.rstrip("/").split("/")[-2]
    return value if len(value) == 64 else None


def _check_free_space(directory: Path, required_bytes: int) -> None:
    free_bytes = shutil.disk_usage(directory).free
    if free_bytes < required_bytes:
        raise RuntimeError(
            f"Not enough free space on {directory.drive or directory.anchor}. "
            f"Need about {required_bytes / 1073741824:.1f} GB, but only "
            f"{free_bytes / 1073741824:.1f} GB is available."
        )


def ensure_model_downloaded(
    whisper_module: Any,
    model_name: str,
    model_cache: str | Path,
    progress=None,
    cancel: CancelCheck | None = None,
) -> Path:
    """Download once into a project-local cache using atomic publication."""
    model_url = getattr(whisper_module, "_MODELS", {}).get(model_name)
    if not model_url:
        raise RuntimeError(f"Unknown Whisper model: {model_name}")
    cache_dir = Path(model_cache).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urllib.parse.urlparse(model_url).path).name
    target = cache_dir / filename

    expected_hash = _expected_model_hash(model_url)
    if target.exists() and target.stat().st_size >= 1024 * 1024:
        if expected_hash and _sha256_file(target, cancel) != expected_hash:
            if progress:
                progress(0.30, f"Cached Whisper {model_name} failed validation; downloading a clean copy...")
            target.unlink(missing_ok=True)
        else:
            if progress:
                progress(0.35, f"Whisper {model_name} model already downloaded; loading it...")
            return target
    elif target.exists():
        target.unlink(missing_ok=True)

    if progress:
        progress(0.30, f"Downloading Whisper {model_name} model to the project cache...")
    partial = cache_dir / f".{filename}.download"
    last_error: BaseException | None = None
    for attempt in range(1, _MODEL_DOWNLOAD_ATTEMPTS + 1):
        try:
            check_cancelled(cancel)
            start = partial.stat().st_size if partial.exists() else 0
            headers = {"User-Agent": "JanesCriber/1.0"}
            if start:
                headers["Range"] = f"bytes={start}-"
            request = urllib.request.Request(model_url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                resumed = bool(start and getattr(response, "status", None) == 206)
                if start and not resumed:
                    start = 0
                content_length = response.headers.get("Content-Length")
                remaining = int(content_length) if content_length and content_length.isdigit() else 0
                total = start + remaining if resumed else remaining
                _check_free_space(cache_dir, max(_MIN_MODEL_FREE_SPACE, remaining + 256 * 1024 * 1024))
                digest = hashlib.sha256()
                if start:
                    with partial.open("rb") as existing:
                        while True:
                            check_cancelled(cancel)
                            chunk = existing.read(1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                received = start
                mode = "ab" if resumed else "wb"
                with partial.open(mode) as handle:
                    while True:
                        check_cancelled(cancel)
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
                        if progress:
                            if total:
                                progress(0.30 + min(0.10, 0.10 * received / total), f"Downloading Whisper {model_name}: {received / 1048576:.0f} / {total / 1048576:.0f} MB")
                            else:
                                progress(0.30, f"Downloading Whisper {model_name}: {received / 1048576:.0f} MB")
                if total and received != total:
                    raise RuntimeError(f"download ended early ({received} of {total} bytes received)")
                if expected_hash and digest.hexdigest() != expected_hash:
                    partial.unlink(missing_ok=True)
                    raise RuntimeError("download checksum did not match the Whisper model")
            os.replace(partial, target)
            return target
        except PipelineAborted:
            raise
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 416:
                partial.unlink(missing_ok=True)
        except (OSError, urllib.error.URLError, RuntimeError) as exc:
            last_error = exc
        if attempt < _MODEL_DOWNLOAD_ATTEMPTS:
            if progress:
                progress(0.30, f"Model download attempt {attempt} failed; retrying ({attempt + 1}/{_MODEL_DOWNLOAD_ATTEMPTS})...")
            time.sleep(float(attempt))
    if isinstance(last_error, RuntimeError) and "Not enough free space" in str(last_error):
        raise last_error
    raise RuntimeError(
        f"Whisper model download failed after {_MODEL_DOWNLOAD_ATTEMPTS} attempts. "
        f"Check internet access and available disk space. ({last_error})"
    ) from last_error


def load_whisper_model(
    whisper_module: Any,
    model_name: str,
    model_cache: str | Path,
    device: str,
    *,
    torch_module: Any,
    progress=None,
    cancel: CancelCheck | None = None,
) -> Any:
    """Construct on CPU first, then transfer to the selected accelerator."""
    check_cancelled(cancel)
    if progress:
        progress(0.40, f"Constructing Whisper {model_name} safely on CPU before {device.upper()} transfer...")
    model = whisper_module.load_model(model_name, device="cpu", download_root=str(model_cache))
    check_cancelled(cancel)
    if device != "cpu":
        clear_accelerator_cache(torch_module, device)
        if progress:
            progress(0.42, f"Moving Whisper {model_name} into {device.upper()} memory...")
        model = model.to(resolve_accelerator_device(device, torch_module))
    check_cancelled(cancel)
    return model
