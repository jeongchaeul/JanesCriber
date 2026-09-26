"""Prevent multiple JanesCriber GUI processes from competing for hardware."""

from __future__ import annotations

import atexit
import os


_mutex_handle = None
_lock_file_fd = None


def acquire_gui_instance(name: str = "JanesCriber.GUI") -> bool:
    """Acquire a per-user single-instance lock, returning False when already running."""
    global _mutex_handle, _lock_file_fd
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.GetLastError.restype = ctypes.c_uint32
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel32.CreateMutexW(None, False, name)
            if not handle:
                return True
            if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                kernel32.CloseHandle(handle)
                return False
            _mutex_handle = handle
            atexit.register(_release_mutex)
            return True
        except (AttributeError, OSError):
            return True

    # Unix (Linux / macOS)
    try:
        import fcntl
        import tempfile
        from pathlib import Path

        lock_path = Path(tempfile.gettempdir()) / f"{name.lower()}.lock"
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            os.close(fd)
            return False
        _lock_file_fd = fd
        atexit.register(_release_mutex)
        return True
    except (ImportError, OSError):
        return True


def _release_mutex() -> None:
    global _mutex_handle, _lock_file_fd
    if _mutex_handle:
        try:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        except (AttributeError, OSError):
            pass
        _mutex_handle = None

    if _lock_file_fd is not None:
        try:
            import fcntl

            fcntl.flock(_lock_file_fd, fcntl.LOCK_UN)
            os.close(_lock_file_fd)
        except (ImportError, OSError):
            pass
        _lock_file_fd = None
