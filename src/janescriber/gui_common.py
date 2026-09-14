"""Thread-safe Tk callbacks used by background transcription workers."""

from __future__ import annotations

import tkinter as tk


def post_to_tk(widget, callback) -> None:
    """Schedule a callback on Tk's main thread without touching widgets off-thread."""
    try:
        if not widget.winfo_exists():
            return
        widget.after(0, callback)
    except (tk.TclError, RuntimeError):
        pass

