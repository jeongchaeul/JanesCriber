"""Small native Windows file-drop bridge for the Tk desktop window."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Callable


class WindowsFileDrop:
    """Receive files dropped on a Tk top-level without a third-party Tcl package."""

    _WM_DROPFILES = 0x0233
    _GWL_WNDPROC = -4

    def __init__(self, widget, on_files: Callable[[list[Path]], None]) -> None:
        self.widget = widget
        self.on_files = on_files
        self.hwnd: int | None = None
        self._old_proc = None
        self._wnd_proc = None
        self._wnd_proc_type = None
        self._user32 = None
        self._shell32 = None
        self._set_window_long = None
        self._call_window_proc = None
        self._drag_accept_files = None
        self._drag_query_file = None
        self._drag_finish = None

    def enable(self) -> bool:
        """Enable native file drops; return False on unsupported platforms."""
        if os.name != "nt":
            return False
        try:
            self.widget.update_idletasks()
            self.hwnd = int(self.widget.winfo_id())
            self._user32 = ctypes.windll.user32
            self._shell32 = ctypes.windll.shell32
            pointer_type = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
            self._wnd_proc_type = ctypes.WINFUNCTYPE(
                pointer_type,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            )

            set_window_long = getattr(self._user32, "SetWindowLongPtrW", None)
            if set_window_long is None:
                set_window_long = self._user32.SetWindowLongW
            set_window_long.restype = ctypes.c_void_p
            set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            self._set_window_long = set_window_long

            call_window_proc = self._user32.CallWindowProcW
            call_window_proc.restype = pointer_type
            call_window_proc.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ]
            self._call_window_proc = call_window_proc

            drag_accept_files = self._user32.DragAcceptFiles
            drag_accept_files.argtypes = [ctypes.c_void_p, ctypes.c_bool]
            self._drag_accept_files = drag_accept_files

            drag_query_file = self._shell32.DragQueryFileW
            drag_query_file.restype = ctypes.c_uint
            drag_query_file.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
            self._drag_query_file = drag_query_file

            drag_finish = self._shell32.DragFinish
            drag_finish.argtypes = [ctypes.c_void_p]
            self._drag_finish = drag_finish

            self._wnd_proc = self._wnd_proc_type(self._window_proc)
            self._old_proc = self._set_window_long(
                ctypes.c_void_p(self.hwnd),
                self._GWL_WNDPROC,
                ctypes.cast(self._wnd_proc, ctypes.c_void_p),
            )
            self._drag_accept_files(ctypes.c_void_p(self.hwnd), True)
            return True
        except Exception:
            self.disable()
            return False

    def disable(self) -> None:
        if self.hwnd is None:
            return
        try:
            if self._drag_accept_files:
                self._drag_accept_files(ctypes.c_void_p(self.hwnd), False)
            if self._old_proc and self._set_window_long:
                self._set_window_long(
                    ctypes.c_void_p(self.hwnd),
                    self._GWL_WNDPROC,
                    ctypes.c_void_p(self._old_proc),
                )
        except Exception:
            pass
        finally:
            self.hwnd = None
            self._old_proc = None
            self._wnd_proc = None

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == self._WM_DROPFILES:
            try:
                paths = self._read_drop_paths(wparam)
                if paths:
                    self.widget.after_idle(lambda paths=paths: self.on_files(paths))
            except Exception:
                pass
            return 0
        if self._old_proc and self._call_window_proc:
            return self._call_window_proc(self._old_proc, hwnd, message, wparam, lparam)
        return 0

    def _read_drop_paths(self, hdrop) -> list[Path]:
        count = self._drag_query_file(ctypes.c_void_p(hdrop), 0xFFFFFFFF, None, 0)
        paths: list[Path] = []
        for index in range(count):
            length = self._drag_query_file(ctypes.c_void_p(hdrop), index, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            self._drag_query_file(ctypes.c_void_p(hdrop), index, buffer, length + 1)
            if buffer.value:
                paths.append(Path(buffer.value))
        self._drag_finish(ctypes.c_void_p(hdrop))
        return paths
