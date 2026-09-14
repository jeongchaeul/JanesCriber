"""Cooperative cancellation and responsive subprocess termination."""

from __future__ import annotations

import subprocess
from typing import Any, Callable


class PipelineAborted(Exception):
    """Raised when the user cancels a transcription job."""


CancelCheck = Callable[[], bool] | Any


def is_cancelled(cancel_check: CancelCheck | None) -> bool:
    """Support threading.Event instances, callables, and boolean flags."""
    if cancel_check is None:
        return False
    if hasattr(cancel_check, "is_set"):
        return bool(cancel_check.is_set())
    if callable(cancel_check):
        return bool(cancel_check())
    return bool(cancel_check) if isinstance(cancel_check, bool) else False


def check_cancelled(cancel_check: CancelCheck | None) -> None:
    if is_cancelled(cancel_check):
        raise PipelineAborted("Operation was cancelled by the user.")


def run_cancellable_subprocess(
    command: list[str],
    cancel_check: CancelCheck | None = None,
    *,
    poll_interval: float = 0.1,
    **popen_kwargs: Any,
) -> tuple[bytes, bytes]:
    """Run an external tool while allowing a job to terminate it promptly."""
    check_cancelled(cancel_check)
    popen_kwargs.setdefault("stdout", subprocess.PIPE)
    popen_kwargs.setdefault("stderr", subprocess.PIPE)
    popen_kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))

    try:
        process = subprocess.Popen(command, **popen_kwargs)
    except FileNotFoundError as exc:
        executable = command[0] if command else "external tool"
        raise RuntimeError(
            f"'{executable}' was not found. Install FFmpeg and confirm that "
            "ffmpeg -version works in a terminal."
        ) from exc

    try:
        while True:
            if is_cancelled(cancel_check):
                _terminate_process(process)
                raise PipelineAborted("External process cancelled by the user.")
            try:
                stdout, stderr = process.communicate(timeout=max(0.02, poll_interval))
                break
            except subprocess.TimeoutExpired:
                continue

        if process.returncode:
            raise subprocess.CalledProcessError(
                process.returncode,
                command,
                output=stdout,
                stderr=stderr,
            )
        return stdout or b"", stderr or b""
    except PipelineAborted:
        raise
    except BaseException:
        if process.poll() is None:
            _terminate_process(process)
        raise


def _terminate_process(process: subprocess.Popen[Any]) -> None:
    try:
        process.terminate()
        process.wait(timeout=1.5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=1.0)
        except (OSError, subprocess.TimeoutExpired):
            pass
