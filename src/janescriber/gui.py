"""Janes family desktop console for transcription."""

from __future__ import annotations

import os
import multiprocessing
import queue
import re
import sys
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from datetime import datetime

import customtkinter as ctk

from .cancellation import PipelineAborted
from .file_drop import WindowsFileDrop
from .hardware import detect_hardware
from .hardware_monitor import HardwareTelemetrySnapshot, SystemHardwareMonitor
from .gui_common import post_to_tk
from .languages import ALL_AVAILABLE_LANGUAGES, LANGUAGE_PRESETS
from .library import TranscriptEntry, discover_transcripts, is_managed_transcript, read_transcript
from .live import (
    CaptureSource,
    LiveSegment,
    LiveProcessController,
    LiveTranscriptionConfig,
    list_application_sources,
    list_microphone_sources,
    list_system_output_sources,
)
from .paths import project_dir, resource_dir, runtime_paths
from .launcher import FRONTEND_MAIN, FRONTEND_PYTHON, relaunch_command, write_frontend_preference
from .pipeline import run_transcription_job
from .vosk_backend import VOSK_LANGUAGE_TO_MODEL, VOSK_MODEL_LABELS, default_model_for_language
from .wav2vec_backend import WAV2VEC2_MODEL_LABELS
from .qwen_backend import QWEN_MODEL_LABELS


THEME = {
    "bg": "#02000a",
    "card": "#090814",
    "inner": "#0f0e1f",
    "border": "#1b192e",
    "glow": "#282540",
    "magenta": "#e82c75",
    "magenta_hover": "#cf2064",
    "cyan": "#3b82f6",
    "cyan_hover": "#2563eb",
    "text": "#ededed",
    "muted": "#9ca3af",
    "input": "#05040d",
    "success": "#10b981",
    "yellow": "#facc15",
}

ASR_ENGINE_OPTIONS = ["Whisper (OpenAI)", "Qwen3-ASR (multilingual)", "Vosk / Kaldi (local)", "Wav2Vec2 (GPU-capable)"]
WHISPER_MODEL_OPTIONS = ["turbo", "large-v3", "medium", "small", "base", "tiny"]


class ConsoleRedirector:
    """Convert stdout/stderr writes, including tqdm carriage returns, to log lines."""

    def __init__(self, sink) -> None:
        self.sink = sink
        self.buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        normalized = text.replace("\r", "\n")
        self.buffer += normalized
        parts = self.buffer.split("\n")
        self.buffer = parts.pop()
        for part in parts:
            if part.strip():
                self.sink(part)
        return len(text)

    def flush(self) -> None:
        if self.buffer.strip():
            self.sink(self.buffer)
        self.buffer = ""


class JanesCriberApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("JanesCriber - AI Transcription Studio")
        self.geometry("1180x780")
        self.minsize(980, 680)
        self.configure(fg_color=THEME["bg"])
        self.paths = runtime_paths()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._diagnostic_log = self.paths["logs"] / "janescriber.log"
        self._diagnostic_log_lock = threading.Lock()
        self.mp_context = multiprocessing.get_context("spawn")
        self.cancel_event = self.mp_context.Event()
        self.worker: threading.Thread | None = None
        self.job_process: multiprocessing.Process | None = None
        self.job_events = None
        self.last_output: Path | None = None
        self.sidebar_collapsed = False
        self.sidebar_animation_id = None
        self.selected_transcript: Path | None = None
        self.selected_language_codes: list[str] = []
        self.console_history: list[str] = []
        self.console_text_widgets: list[ctk.CTkTextbox] = []
        self.is_processing = False
        self.live_session: LiveTranscriber | None = None
        self.start_processing_time = 0.0
        self.hw_info = detect_hardware()
        self.hw_monitor = SystemHardwareMonitor()
        self.file_drop = WindowsFileDrop(self, self._handle_dropped_files)
        self._set_icon()
        self._build_ui()
        if self.file_drop.enable():
            self._log("Drag-and-drop ready: drop an audio or video file anywhere on this window.")
        self._log(f"JanesCriber ready. Program folder: {self.paths['base']}")
        self._log("Select a media file and press Transcribe to begin.")
        self._drain_logs()
        self._refresh_hardware()
        self.hw_monitor.start(
            callback=lambda snapshot: post_to_tk(self, lambda snap=snapshot: self._apply_hardware_stats(snap)),
            interval=1.5,
        )

    def _set_icon(self) -> None:
        icon = resource_dir() / "assets" / "icon.png"
        if icon.exists():
            try:
                from PIL import Image, ImageTk
                self._icon_image = ImageTk.PhotoImage(Image.open(icon))
                self.iconphoto(True, self._icon_image)
            except Exception:
                pass

    def _button(self, parent, text, command, *, primary=False, width=130):
        return ctk.CTkButton(parent, text=text, command=command, width=width, height=34,
                             fg_color=THEME["magenta"] if primary else THEME["glow"],
                             hover_color=THEME["magenta_hover"] if primary else THEME["cyan"],
                             font=ctk.CTkFont(size=11, weight="bold"))

    def _build_ui(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=235, corner_radius=0, fg_color=THEME["card"])
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=THEME["bg"])
        self.content.pack(side="left", fill="both", expand=True, padx=20, pady=18)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._build_studio()

    def _build_sidebar(self) -> None:
        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=10, pady=(12, 8))
        self.sidebar_heading = ctk.CTkLabel(sidebar_header, text="WORKSPACE", text_color=THEME["muted"], font=ctk.CTkFont(size=10, weight="bold"))
        self.sidebar_heading.pack(side="left", padx=8)
        self.sidebar_toggle = ctk.CTkButton(sidebar_header, text="‹", width=30, height=28, corner_radius=7,
                                            fg_color=THEME["input"], hover_color=THEME["glow"],
                                            text_color=THEME["text"], font=ctk.CTkFont(size=20, weight="bold"),
                                            command=self._toggle_sidebar)
        self.sidebar_toggle.pack(side="right")

        logo_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_row.pack(fill="x", padx=18, pady=(24, 10))
        self.logo_row = logo_row
        try:
            from PIL import Image
            image = Image.open(project_dir() / "assets" / "icon.png")
            self._logo = ctk.CTkImage(light_image=image, dark_image=image, size=(54, 54))
            ctk.CTkLabel(logo_row, image=self._logo, text="").pack(side="left")
        except Exception:
            ctk.CTkLabel(logo_row, text="◈", text_color=THEME["magenta"], font=ctk.CTkFont(size=40, weight="bold")).pack(side="left")
        self.logo_name_frame = ctk.CTkFrame(logo_row, fg_color="transparent")
        self.logo_name_frame.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(self.logo_name_frame, text="JanesCriber", text_color=THEME["text"], font=ctk.CTkFont(size=19, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self.logo_name_frame, text="JANE MEDIA SUITE", text_color=THEME["cyan"], font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w")

        self.nav_buttons = {}
        self.sidebar_tab_icons = {"studio": "◉", "live": "◌", "library": "▣", "hardware": "▦", "console": "▤"}
        nav_items = (("studio", "◉  Transcription Studio"), ("live", "◌  Live Transcription"), ("library", "▣  Transcript Library"), ("hardware", "▦  Hardware & Pipeline"), ("console", "▤  Console Logs"))
        for key, label in nav_items:
            button = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=38, corner_radius=6,
                                   fg_color=THEME["magenta"] if key == "studio" else "transparent",
                                   hover_color=THEME["glow"], text_color=THEME["text"],
                                   command=lambda k=key: self._select_view(k))
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = button

        self.sidebar_divider = ctk.CTkFrame(self.sidebar, height=1, fg_color=THEME["border"])
        self.sidebar_divider.pack(fill="x", padx=18, pady=18)
        self.sidebar_engine_heading = ctk.CTkLabel(self.sidebar, text="LOCAL-FIRST ENGINE", text_color=THEME["muted"], font=ctk.CTkFont(size=10, weight="bold"))
        self.sidebar_engine_heading.pack(anchor="w", padx=20)
        self.sidebar_engine_description = ctk.CTkLabel(self.sidebar, text="Whisper runs on your machine.\nModels, cache and scratch files\nstay in the project folder.", justify="left", text_color=THEME["muted"], font=ctk.CTkFont(size=11), wraplength=190)
        self.sidebar_engine_description.pack(anchor="w", padx=20, pady=(6, 0))
        self.interface_controls = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.interface_controls.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        ctk.CTkFrame(self.interface_controls, height=1, fg_color=THEME["border"]).pack(fill="x", padx=6, pady=(0, 8))
        self.interface_heading = ctk.CTkLabel(self.interface_controls, text="INTERFACE", text_color=THEME["muted"], font=ctk.CTkFont(size=10, weight="bold"))
        self.interface_heading.pack(anchor="w", padx=8, pady=(0, 5))
        self.main_interface_btn = ctk.CTkButton(self.interface_controls, text="▣  Use Main UI Next Launch", anchor="w", height=28, corner_radius=7, fg_color=THEME["inner"], hover_color=THEME["glow"], border_width=1, border_color=THEME["border"], text_color=THEME["text"], font=ctk.CTkFont(size=10, weight="bold"), command=lambda: self._set_interface_preference(FRONTEND_MAIN, "Main UI"))
        self.main_interface_btn.pack(fill="x", pady=(0, 4))
        self.legacy_interface_btn = ctk.CTkButton(self.interface_controls, text="▤  Use Legacy Python Next Launch", anchor="w", height=28, corner_radius=7, fg_color=THEME["inner"], hover_color=THEME["glow"], border_width=1, border_color=THEME["border"], text_color=THEME["text"], font=ctk.CTkFont(size=10, weight="bold"), command=lambda: self._set_interface_preference(FRONTEND_PYTHON, "Legacy Python UI"))
        self.legacy_interface_btn.pack(fill="x", pady=(0, 4))
        self.relaunch_btn = ctk.CTkButton(self.interface_controls, text="↻  Relaunch JanesCriber", anchor="w", height=28, corner_radius=7, fg_color=THEME["inner"], hover_color=THEME["glow"], border_width=1, border_color=THEME["border"], text_color=THEME["text"], font=ctk.CTkFont(size=10, weight="bold"), command=self._relaunch)
        self.relaunch_btn.pack(fill="x")
        self.sidebar_status = ctk.CTkLabel(self.sidebar, text="● READY", text_color=THEME["success"], font=ctk.CTkFont(size=11, weight="bold"))
        self.sidebar_status.pack(side="bottom", anchor="w", padx=20, pady=24)

    def _toggle_sidebar(self) -> None:
        """Animate the workspace sidebar between expanded and compact modes."""
        if self.sidebar_animation_id is not None:
            return
        self.sidebar_collapsed = not self.sidebar_collapsed
        target = 58 if self.sidebar_collapsed else 235
        start = self.sidebar.winfo_width() or (235 if not self.sidebar_collapsed else 58)
        direction = 1 if target > start else -1
        self.sidebar_toggle.configure(state="disabled")

        def animate(width: int):
            distance = abs(target - width)
            if distance <= 10:
                self.sidebar.configure(width=target)
                self.sidebar_animation_id = None
                self.sidebar_toggle.configure(state="normal", text="›" if self.sidebar_collapsed else "‹")
                self._apply_sidebar_compact_mode()
                return
            next_width = width + direction * min(14, distance)
            self.sidebar.configure(width=next_width)
            self.sidebar_animation_id = self.after(12, lambda: animate(next_width))

        animate(start)

    def _apply_sidebar_compact_mode(self) -> None:
        compact = self.sidebar_collapsed
        self.sidebar_heading.configure(text="" if compact else "WORKSPACE")
        if compact:
            self.logo_name_frame.pack_forget()
            self.logo_row.pack_configure(padx=2)
            self.sidebar_divider.pack_forget()
            self.sidebar_engine_heading.pack_forget()
            self.sidebar_engine_description.pack_forget()
            self.interface_heading.configure(text="")
            self.interface_controls.pack_configure(padx=8)
            self.main_interface_btn.configure(text="M", width=32, anchor="center")
            self.legacy_interface_btn.configure(text="P", width=32, anchor="center")
            self.relaunch_btn.configure(text="↻", width=32, anchor="center")
            self.sidebar_status.configure(text="●", anchor="center")
            self.sidebar_status.pack_configure(anchor="center", padx=0)
            try:
                self._logo.configure(size=(42, 42))
            except Exception:
                pass
        else:
            self.logo_name_frame.pack(side="left", padx=(10, 0))
            self.logo_row.pack_configure(padx=18)
            self.sidebar_divider.pack(fill="x", padx=18, pady=18)
            self.sidebar_engine_heading.pack(anchor="w", padx=20)
            self.sidebar_engine_description.pack(anchor="w", padx=20, pady=(6, 0))
            self.interface_heading.configure(text="INTERFACE")
            self.interface_controls.pack_configure(padx=12)
            self.main_interface_btn.configure(text="▣  Use Main UI Next Launch", width=0, anchor="w")
            self.legacy_interface_btn.configure(text="▤  Use Legacy Python Next Launch", width=0, anchor="w")
            self.relaunch_btn.configure(text="↻  Relaunch JanesCriber", width=0, anchor="w")
            self.sidebar_status.configure(text="● READY", anchor="w")
            self.sidebar_status.pack_configure(anchor="w", padx=20)
            try:
                self._logo.configure(size=(54, 54))
            except Exception:
                pass
        for key, button in self.nav_buttons.items():
            button.configure(text=self.sidebar_tab_icons[key] if compact else dict((k, v) for k, v in (("studio", "◉  Transcription Studio"), ("live", "◌  Live Transcription"), ("library", "▣  Transcript Library"), ("hardware", "▦  Hardware & Pipeline"), ("console", "▤  Console Logs")))[key], anchor="center" if compact else "w")
            button.pack_configure(padx=10 if not compact else 8)

    def _set_interface_preference(self, preference: str, label: str) -> None:
        try:
            write_frontend_preference(preference, self.paths["base"])
            self.sidebar_status.configure(text=f"● {label.upper()} NEXT LAUNCH", text_color=THEME["yellow"])
            messagebox.showinfo("Interface Preference", f"{label} will open the next time JanesCriber starts.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Interface Preference", f"Could not save the interface preference.\n\n{exc}")

    def _relaunch(self) -> None:
        if self.is_processing or (self.live_session and self.live_session.is_running):
            messagebox.showwarning("Transcription in Progress", "Stop the current transcription or live session before relaunching JanesCriber.")
            return
        environment = os.environ.copy()
        environment["JANESCRIBER_DATA_DIR"] = str(self.paths["base"])
        launch_kwargs: dict[str, object] = {
            "cwd": str(self.paths["base"]),
            "env": environment,
            "close_fds": os.name != "nt",
        }
        if os.name == "nt":
            launch_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(relaunch_command(self.paths["base"]), **launch_kwargs)
        except OSError as exc:
            messagebox.showerror("Relaunch failed", f"JanesCriber could not be relaunched.\n\n{exc}")
            return
        self.destroy()

    def _card(self, parent, title, subtitle=""):
        card = ctk.CTkFrame(parent, fg_color=THEME["card"], border_width=1, border_color=THEME["border"], corner_radius=10)
        ctk.CTkLabel(card, text=title, text_color=THEME["text"], font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(14, 0))
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, text_color=THEME["muted"], font=ctk.CTkFont(size=11), justify="left").pack(anchor="w", padx=16, pady=(3, 10))
        return card

    @staticmethod
    def _engine_id(menu) -> str:
        value = str(menu.get())
        if value.startswith("Vosk"):
            return "vosk"
        if value.startswith("Wav2Vec2"):
            return "wav2vec2"
        if value.startswith("Qwen3"):
            return "qwen3-asr"
        return "whisper"

    @staticmethod
    def _model_id(menu) -> str:
        value = str(menu.get())
        for model_id, label in VOSK_MODEL_LABELS.items():
            if value == label:
                return model_id
        for model_id, label in WAV2VEC2_MODEL_LABELS.items():
            if value == label:
                return model_id
        for model_id, label in QWEN_MODEL_LABELS.items():
            if value == label:
                return model_id
        return value

    def _configure_asr_model_menu(self, menu, engine: str, *, default: str | None = None) -> None:
        if engine == "vosk":
            values = list(VOSK_MODEL_LABELS.values())
            model_id = default if default in VOSK_MODEL_LABELS else "en-us-small"
            menu.configure(values=values)
            menu.set(VOSK_MODEL_LABELS[model_id])
        elif engine == "wav2vec2":
            values = list(WAV2VEC2_MODEL_LABELS.values())
            model_id = default if default in WAV2VEC2_MODEL_LABELS else "wav2vec2-base-960h"
            menu.configure(values=values)
            menu.set(WAV2VEC2_MODEL_LABELS[model_id])
        elif engine == "qwen3-asr":
            values = list(QWEN_MODEL_LABELS.values())
            model_id = default if default in QWEN_MODEL_LABELS else "qwen3-asr-0.6b"
            menu.configure(values=values)
            menu.set(QWEN_MODEL_LABELS[model_id])
        else:
            menu.configure(values=WHISPER_MODEL_OPTIONS)
            menu.set(default if default in WHISPER_MODEL_OPTIONS else "turbo")

    def _sync_vosk_model_for_language(self, menu, codes: list[str]) -> None:
        if self._engine_id(menu) != "vosk" or not codes:
            return
        model_id = VOSK_LANGUAGE_TO_MODEL.get(codes[0])
        if model_id:
            menu.set(VOSK_MODEL_LABELS[model_id])

    def _on_studio_engine_changed(self, choice: str) -> None:
        engine = self._engine_id(self.engine_menu)
        self._configure_asr_model_menu(self.model_menu, engine)
        if engine == "vosk":
            self.engine_help.configure(text="Vosk / Kaldi runs fully locally without an OpenAI model or cloud API. Choose one supported language.")
            self._sync_vosk_model_for_language(self.model_menu, self.selected_language_codes)
        elif engine == "wav2vec2":
            self.engine_help.configure(text="Wav2Vec2 is a local GPU-capable English option using the existing Torch runtime. It falls back to CPU.")
        elif engine == "qwen3-asr":
            self.engine_help.configure(text="Qwen3-ASR is an optional local multilingual model with Filipino support and GPU acceleration. It uses bounded timestamp blocks; exact word timing remains a Whisper feature.")
        else:
            self.engine_help.configure(text="Whisper runs locally and offers the broadest language coverage and strongest accuracy.")

    def _on_live_engine_changed(self, choice: str) -> None:
        engine = self._engine_id(self.live_engine_menu)
        default = "tiny" if engine == "whisper" else ("qwen3-asr-0.6b" if engine == "qwen3-asr" else ("en-us-small" if engine == "vosk" else "wav2vec2-base-960h"))
        self._configure_asr_model_menu(self.live_model_menu, engine, default=default)
        if engine == "vosk":
            self.live_engine_help.configure(text="Vosk / Kaldi is a lightweight local backend. It uses one language model at a time.")
            self._sync_vosk_model_for_language(self.live_model_menu, self.selected_language_codes)
        elif engine == "wav2vec2":
            self.live_engine_help.configure(text="Wav2Vec2 is a local GPU-capable English backend. It falls back to CPU when CUDA is unavailable.")
        elif engine == "qwen3-asr":
            self.live_engine_help.configure(text="Qwen3-ASR is available for file transcription only. Use Whisper, Vosk, or Wav2Vec2 for live sessions.")
        else:
            self.live_engine_help.configure(text="Whisper provides broader language coverage; Tiny or Base is recommended for long sessions.")

    def _build_studio(self) -> None:
        self.studio = ctk.CTkFrame(self.content, fg_color="transparent")
        self.studio.grid(row=0, column=0, sticky="nsew")
        self.studio.grid_columnconfigure(0, weight=3)
        self.studio.grid_columnconfigure(1, weight=2)
        self.studio.grid_rowconfigure(2, weight=1)

        source = self._card(self.studio, "1. Choose audio or video", "Every format FFmpeg can read is accepted. Drop a file anywhere on this window or use Browse. The .txt result is written in JanesCriber\\Transcripts.")
        source.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        row = ctk.CTkFrame(source, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 15))
        self.source_entry = ctk.CTkEntry(row, placeholder_text="Select a media file...", height=38, fg_color=THEME["input"], border_color=THEME["border"])
        self.source_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._button(row, "Browse…", self._browse, width=105).pack(side="right")

        options = self._card(self.studio, "2. Transcription settings", "Whisper uses GPU acceleration when available; Vosk / Kaldi is lightweight CPU; Wav2Vec2 adds a local GPU-capable English option.")
        options.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        form = ctk.CTkFrame(options, fg_color="transparent")
        form.pack(fill="x", padx=16, pady=(0, 14))
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text="ASR engine", text_color=THEME["muted"]).grid(row=0, column=0, sticky="w", pady=7)
        self.engine_menu = ctk.CTkOptionMenu(
            form,
            values=ASR_ENGINE_OPTIONS,
            command=self._on_studio_engine_changed,
            fg_color=THEME["input"],
            button_color=THEME["glow"],
            button_hover_color=THEME["cyan"],
        )
        self.engine_menu.set(ASR_ENGINE_OPTIONS[0])
        self.engine_menu.grid(row=0, column=1, sticky="ew", padx=(18, 0), pady=4)
        ctk.CTkLabel(form, text="Model", text_color=THEME["muted"]).grid(row=1, column=0, sticky="w", pady=7)
        self.model_menu = ctk.CTkOptionMenu(form, values=WHISPER_MODEL_OPTIONS, fg_color=THEME["input"], button_color=THEME["glow"], button_hover_color=THEME["cyan"])
        self.model_menu.set("turbo")
        self.model_menu.grid(row=1, column=1, sticky="ew", padx=(18, 0), pady=4)
        self.engine_help = ctk.CTkLabel(form, text="Whisper runs locally and offers the broadest language coverage and strongest accuracy.", text_color=THEME["muted"], justify="left", anchor="w", wraplength=360)
        self.engine_help.grid(row=2, column=1, sticky="w", padx=(18, 0), pady=(0, 4))
        ctk.CTkLabel(form, text="Spoken language", text_color=THEME["muted"]).grid(row=3, column=0, sticky="w", pady=7)
        language_row = ctk.CTkFrame(form, fg_color="transparent")
        language_row.grid(row=3, column=1, sticky="ew", padx=(18, 0), pady=4)
        language_row.grid_columnconfigure(0, weight=1)
        self.language_menu = ctk.CTkOptionMenu(
            language_row,
            values=list(LANGUAGE_PRESETS.keys()),
            command=self._on_language_menu_select,
            fg_color=THEME["input"],
            button_color=THEME["glow"],
            button_hover_color=THEME["cyan"],
            height=32,
        )
        self.language_menu.set("Auto-Detect (Best Available Detection)")
        self.language_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.custom_language_button = ctk.CTkButton(
            language_row,
            text="🔀 Multi...",
            width=82,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=THEME["glow"],
            hover_color=THEME["cyan"],
            command=self._open_multi_language_modal,
        )
        self.custom_language_button.grid(row=0, column=1, sticky="e")
        self.overwrite = ctk.BooleanVar(value=False)
        self.cache = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(form, text="Overwrite same-name .txt", variable=self.overwrite, text_color=THEME["muted"], fg_color=THEME["magenta"], hover_color=THEME["magenta_hover"]).grid(row=4, column=0, columnspan=2, sticky="w", pady=(9, 2))
        ctk.CTkCheckBox(form, text="Use local transcript cache", variable=self.cache, text_color=THEME["muted"], fg_color=THEME["cyan"], hover_color=THEME["cyan_hover"]).grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

        action = self._card(self.studio, "3. Generate transcript", "")
        action.grid(row=1, column=1, sticky="nsew", pady=(0, 12))
        self.progress = ctk.CTkProgressBar(action, progress_color=THEME["magenta"], fg_color=THEME["input"])
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(12, 9))
        self.status = ctk.CTkLabel(action, text="Ready for a media file.", text_color=THEME["muted"], wraplength=240, justify="left")
        self.status.pack(anchor="w", padx=16, pady=(0, 12))
        buttons = ctk.CTkFrame(action, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 15))
        self.start_button = self._button(buttons, "▶  Transcribe", self._start, primary=True, width=140)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.cancel_button = self._button(buttons, "Cancel", self._cancel, width=76)
        self.cancel_button.configure(state="disabled")
        self.cancel_button.pack(side="right")

        ctk.CTkLabel(action, text="Output", text_color=THEME["text"], font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=16, pady=(0, 3))
        self.output_label = ctk.CTkLabel(action, text="No transcript generated yet.", text_color=THEME["muted"], justify="left", anchor="w", wraplength=290)
        self.output_label.pack(fill="x", padx=16, pady=(0, 15))

        console_card = self._card(self.studio, "Console Logs", "Live pipeline output and hardware messages.")
        console_card.grid(row=2, column=0, columnspan=2, sticky="nsew")
        studio_console_text = ctk.CTkTextbox(console_card, fg_color="#05040d", text_color="#b9f6ff", font=ctk.CTkFont(family="Consolas", size=11))
        studio_console_text.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.console_text_widgets.append(studio_console_text)

    def _build_live(self) -> None:
        self.live_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.live_frame.grid_columnconfigure(0, weight=1)
        self.live_frame.grid_rowconfigure(1, weight=1)

        controls = self._card(
            self.live_frame,
            "Live Transcription",
            "Choose a microphone, your computer audio, or a visible app and turn speech into timestamped documentation while it is happening.",
        )
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        control_row = ctk.CTkFrame(controls, fg_color="transparent")
        control_row.pack(fill="x", padx=16, pady=(0, 12))
        control_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(control_row, text="Capture mode", text_color=THEME["muted"]).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=5)
        self.live_capture_type_menu = ctk.CTkOptionMenu(
            control_row,
            values=["Microphone", "System output", "Application output"],
            command=self._on_live_capture_type_changed,
            fg_color=THEME["input"],
            button_color=THEME["glow"],
            button_hover_color=THEME["cyan"],
        )
        self.live_capture_type_menu.set("Microphone")
        self.live_capture_type_menu.grid(row=0, column=1, sticky="ew", pady=4)

        ctk.CTkLabel(control_row, text="Capture source", text_color=THEME["muted"]).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=5)
        source_row = ctk.CTkFrame(control_row, fg_color="transparent")
        source_row.grid(row=1, column=1, sticky="ew", pady=4)
        source_row.grid_columnconfigure(0, weight=1)
        self.live_source_values: dict[str, CaptureSource] = {}
        self.live_device_menu = ctk.CTkOptionMenu(
            source_row,
            values=["Default microphone"],
            fg_color=THEME["input"],
            button_color=THEME["glow"],
            button_hover_color=THEME["cyan"],
        )
        self.live_device_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.live_refresh_sources_button = self._button(source_row, "↻", self._refresh_live_capture_sources, width=38)
        self.live_refresh_sources_button.grid(row=0, column=1)
        self.live_capture_help = ctk.CTkLabel(
            control_row,
            text="Microphone captures a physical or virtual input device.",
            text_color=THEME["muted"],
            justify="left",
            anchor="w",
        )
        self.live_capture_help.grid(row=2, column=1, sticky="w", pady=(0, 4))

        ctk.CTkLabel(control_row, text="ASR engine", text_color=THEME["muted"]).grid(row=3, column=0, sticky="w", padx=(0, 12), pady=5)
        self.live_engine_menu = ctk.CTkOptionMenu(
            control_row,
            values=ASR_ENGINE_OPTIONS,
            command=self._on_live_engine_changed,
            fg_color=THEME["input"],
            button_color=THEME["glow"],
            button_hover_color=THEME["cyan"],
        )
        self.live_engine_menu.set(ASR_ENGINE_OPTIONS[0])
        self.live_engine_menu.grid(row=3, column=1, sticky="ew", pady=4)

        ctk.CTkLabel(control_row, text="Model", text_color=THEME["muted"]).grid(row=4, column=0, sticky="w", padx=(0, 12), pady=5)
        self.live_model_menu = ctk.CTkOptionMenu(
            control_row,
            values=WHISPER_MODEL_OPTIONS,
            fg_color=THEME["input"],
            button_color=THEME["glow"],
            button_hover_color=THEME["cyan"],
        )
        self.live_model_menu.set("tiny")
        self.live_model_menu.grid(row=4, column=1, sticky="ew", pady=4)

        self.live_engine_help = ctk.CTkLabel(control_row, text="Whisper provides broader language coverage; Tiny or Base is recommended for long sessions.", text_color=THEME["muted"], justify="left", anchor="w", wraplength=760)
        self.live_engine_help.grid(row=5, column=1, sticky="w", pady=(0, 4))

        ctk.CTkLabel(control_row, text="Languages", text_color=THEME["muted"]).grid(row=6, column=0, sticky="w", padx=(0, 12), pady=5)
        language_actions = ctk.CTkFrame(control_row, fg_color="transparent")
        language_actions.grid(row=6, column=1, sticky="ew", pady=4)
        language_actions.grid_columnconfigure(0, weight=1)
        self.live_language_label = ctk.CTkLabel(language_actions, text="Auto-detect", text_color=THEME["text"], fg_color=THEME["input"], corner_radius=6, anchor="w")
        self.live_language_label.grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=6)
        self._button(language_actions, "Choose languages…", self._open_live_language_modal, width=142).grid(row=0, column=1)

        ctk.CTkLabel(
            controls,
            text="⚠ Live memory guide: Tiny or Base is recommended for long sessions. Small and Turbo use substantially more RAM and may slow live updates.",
            text_color=THEME["yellow"],
            fg_color="#211a08",
            corner_radius=6,
            justify="left",
            anchor="w",
            wraplength=760,
        ).pack(fill="x", padx=16, pady=(2, 10), ipady=6)

        live_actions = ctk.CTkFrame(controls, fg_color="transparent")
        live_actions.pack(fill="x", padx=16, pady=(0, 15))
        self.live_start_button = self._button(live_actions, "●  Start Listening", self._start_live, primary=True, width=170)
        self.live_start_button.pack(side="left")
        self.live_stop_button = self._button(live_actions, "Stop & Save", self._stop_live, width=120)
        self.live_stop_button.configure(state="disabled")
        self.live_stop_button.pack(side="left", padx=(8, 0))
        self.live_status = ctk.CTkLabel(live_actions, text="Ready for an audio source.", text_color=THEME["muted"], anchor="e", justify="right")
        self.live_status.pack(side="right", fill="x", expand=True, padx=(12, 0))

        transcript_card = self._card(self.live_frame, "Live Notes", "The transcript is continuously saved in JanesCriber\\Transcripts.")
        transcript_card.grid(row=1, column=0, sticky="nsew")
        self.live_text = ctk.CTkTextbox(transcript_card, fg_color="#05040d", text_color=THEME["text"], wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self.live_text.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.live_text.tag_config("timestamp", foreground=THEME["magenta"])
        self.live_text.insert("end", "Press Start Listening when you are ready.\n")
        self.live_text.configure(state="disabled")
        self._refresh_live_capture_sources()

    def _on_live_capture_type_changed(self, value: str) -> None:
        self._refresh_live_capture_sources()

    def _refresh_live_capture_sources(self) -> None:
        if not hasattr(self, "live_capture_type_menu"):
            return
        mode = self.live_capture_type_menu.get()
        if mode == "System output":
            sources = list_system_output_sources()
            help_text = "System output captures the audio mix from the selected speaker or headset."
            empty_text = "No loopback output devices found"
        elif mode == "Application output":
            sources = list_application_sources()
            help_text = "Choose a visible app window. PIDs and background processes stay hidden."
            empty_text = "No visible applications found"
        else:
            sources = list_microphone_sources()
            help_text = "Microphone captures a physical or virtual input device."
            empty_text = "No microphone devices found"
            sources.insert(0, CaptureSource("microphone", "Default microphone"))
        self.live_capture_help.configure(text=help_text)
        self.live_source_values = {source.label: source for source in sources}
        labels = list(self.live_source_values) or [empty_text]
        self.live_device_menu.configure(values=labels)
        self.live_device_menu.set(labels[0])
        self.live_refresh_sources_button.configure(state="normal")

    def _show_live(self):
        self._hide_all_views()
        if not hasattr(self, "live_frame"):
            self._build_live()
        self.live_frame.grid(row=0, column=0, sticky="nsew")
        self._update_live_language_label()

    def _update_live_language_label(self) -> None:
        if hasattr(self, "live_language_label"):
            if not self.selected_language_codes:
                label = "Auto-detect"
            else:
                names = [ALL_AVAILABLE_LANGUAGES.get(code, code.upper()).split(" (")[0] for code in self.selected_language_codes]
                label = ", ".join(names)
            self.live_language_label.configure(text=label)

    def _open_live_language_modal(self) -> None:
        self._open_multi_language_modal()
        self.after(50, self._update_live_language_label)

    def _start_live(self) -> None:
        if self.live_session and self.live_session.is_running:
            return
        try:
            config = LiveTranscriptionConfig(
                engine=self._engine_id(self.live_engine_menu),
                model_name=self._model_id(self.live_model_menu),
                language=tuple(self.selected_language_codes),
            )
            capture_source = self.live_source_values.get(self.live_device_menu.get())
            if capture_source is None:
                raise RuntimeError("Choose an available live audio source before starting.")
            self.live_session = LiveProcessController(
                self.paths,
                config,
                capture_source=capture_source,
                on_status=lambda message: post_to_tk(self, lambda value=message: self._live_status(value)),
                on_text=lambda text, segments: post_to_tk(self, lambda value=text: self._set_live_text(value)),
                on_finished=lambda path: post_to_tk(self, lambda value=path: self._live_finished(value)),
                on_error=lambda error: post_to_tk(self, lambda value=error: self._live_failed(value)),
            )
            start_message = (
                f"Starting {self.live_capture_type_menu.get().lower()} and loading "
                f"{config.engine.title()} ({config.model_name})…"
            )
            self._set_live_text(start_message + "\n")
            self._log(f"[LIVE] {start_message}")
            self.live_start_button.configure(state="disabled")
            self.live_stop_button.configure(state="normal")
            self.sidebar_status.configure(text="● LISTENING", text_color=THEME["yellow"])
            self.hw_monitor.set_processing(True)
            self.live_session.start()
        except Exception as exc:
            self._live_failed(exc)

    def _stop_live(self) -> None:
        if self.live_session and self.live_session.is_running:
            self._set_live_status("Stopping audio capture and saving the live transcript…")
            self.live_session.stop()
        elif self.live_session and self.live_session.output_path:
            self._live_finished(self.live_session.output_path if self.live_session else None)

    def _set_live_status(self, message: str) -> None:
        if hasattr(self, "live_status"):
            self.live_status.configure(text=message)

    def _live_status(self, message: str) -> None:
        """Show and persist live-worker stage messages on the Tk thread."""
        self._set_live_status(message)
        self._log(f"[LIVE] {message}")

    def _set_live_text(self, content: str) -> None:
        if not hasattr(self, "live_text"):
            return
        self.live_text.configure(state="normal")
        self.live_text.delete("1.0", "end")
        for line in content.splitlines(keepends=True):
            body = line.rstrip("\r\n")
            ending = line[len(body):]
            if re.fullmatch(r"\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]", body):
                self.live_text.insert("end", body, "timestamp")
                self.live_text.insert("end", ending)
            else:
                self.live_text.insert("end", line)
        self.live_text.see("end")
        self.live_text.configure(state="disabled")

    def _live_finished(self, path: Path | None) -> None:
        self.live_start_button.configure(state="normal")
        self.live_stop_button.configure(state="disabled")
        self.hw_monitor.set_processing(False)
        self.sidebar_status.configure(text="● READY", text_color=THEME["success"])
        if path:
            self._set_live_status(f"Saved live transcript: {path.name}")
            self._log(f"[+] Live transcript saved in Transcripts: {path}")
            if hasattr(self, "library_scroll"):
                self._refresh_library()
        else:
            self._set_live_status("Live transcription stopped.")

    def _live_failed(self, error: BaseException) -> None:
        self.live_start_button.configure(state="normal")
        self.live_stop_button.configure(state="disabled")
        self.hw_monitor.set_processing(False)
        self.sidebar_status.configure(text="● READY", text_color=THEME["success"])
        self._set_live_status(str(error))
        self._log(f"[!] Live transcription: {error}")
        if self.live_session and self.live_session.output_path and self.live_session.output_path.is_file():
            self._refresh_library()

    def _select_view(self, key: str) -> None:
        for name, button in self.nav_buttons.items():
            button.configure(fg_color=THEME["magenta"] if name == key else "transparent")
        if key == "studio":
            self._show_studio()
        elif key == "live":
            self._show_live()
        elif key == "library":
            self._show_library()
        elif key == "hardware":
            self._show_hardware()
        else:
            self._show_console()

    def _hide_all_views(self) -> None:
        """Keep tab frames mutually exclusive in the shared content area."""
        for name in ("studio", "live_frame", "library_frame", "hardware_frame", "console_frame"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.grid_remove()

    def _show_studio(self):
        self._hide_all_views()
        self.studio.grid(row=0, column=0, sticky="nsew")

    def _show_library(self):
        self._hide_all_views()
        if not hasattr(self, "library_frame"):
            self._build_library()
        self.library_frame.grid(row=0, column=0, sticky="nsew")
        self._refresh_library()

    def _show_hardware(self):
        self._hide_all_views()
        if not hasattr(self, "hardware_frame"):
            self._build_hardware()
        self.hardware_frame.grid(row=0, column=0, sticky="nsew")
        self._refresh_hardware()

    def _build_hardware(self) -> None:
        self.hardware_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.hardware_frame.grid_columnconfigure(0, weight=1)
        self.hardware_frame.grid_rowconfigure(2, weight=1)

        overview = self._card(self.hardware_frame, "Live Hardware Monitor", "Task Manager-style telemetry for the host and JanesCriber workload. Values refresh automatically while the program is idle or transcribing.")
        overview.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.hardware_backend_label = ctk.CTkLabel(overview, text="Backend: detecting...", text_color=THEME["cyan"], anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
        self.hardware_backend_label.pack(fill="x", padx=16, pady=(0, 12))
        self.hardware_status_label = ctk.CTkLabel(overview, text="Telemetry is initializing...", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=10))
        self.hardware_status_label.pack(fill="x", padx=16, pady=(0, 12))

        cards = ctk.CTkFrame(self.hardware_frame, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        cards.grid_columnconfigure((0, 1, 2), weight=1)

        cpu_card = ctk.CTkFrame(cards, fg_color=THEME["inner"], corner_radius=10, border_width=1, border_color=THEME["border"])
        cpu_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.cpu_name_label = ctk.CTkLabel(cpu_card, text="⚡ CPU", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
        self.cpu_name_label.pack(fill="x", padx=12, pady=(10, 2))
        self.cpu_value_label = ctk.CTkLabel(cpu_card, text="0.0 %", text_color=THEME["cyan"], anchor="w", font=ctk.CTkFont(size=24, weight="bold"))
        self.cpu_value_label.pack(anchor="w", padx=12)
        self.cpu_progress = ctk.CTkProgressBar(cpu_card, progress_color=THEME["cyan"], fg_color=THEME["input"], height=7)
        self.cpu_progress.set(0)
        self.cpu_progress.pack(fill="x", padx=12, pady=(6, 6))
        self.cpu_detail_label = ctk.CTkLabel(cpu_card, text="System load • App: 0.0%", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=10))
        self.cpu_detail_label.pack(fill="x", padx=12, pady=(0, 10))

        ram_card = ctk.CTkFrame(cards, fg_color=THEME["inner"], corner_radius=10, border_width=1, border_color=THEME["border"])
        ram_card.grid(row=0, column=1, sticky="nsew", padx=5)
        self.ram_name_label = ctk.CTkLabel(ram_card, text="💾 System RAM", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
        self.ram_name_label.pack(fill="x", padx=12, pady=(10, 2))
        self.ram_value_label = ctk.CTkLabel(ram_card, text="0.0 %", text_color="#a855f7", anchor="w", font=ctk.CTkFont(size=24, weight="bold"))
        self.ram_value_label.pack(anchor="w", padx=12)
        self.ram_progress = ctk.CTkProgressBar(ram_card, progress_color="#a855f7", fg_color=THEME["input"], height=7)
        self.ram_progress.set(0)
        self.ram_progress.pack(fill="x", padx=12, pady=(6, 6))
        self.ram_detail_label = ctk.CTkLabel(ram_card, text="0.0 GB / 0.0 GB • App: 0 MB", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=10))
        self.ram_detail_label.pack(fill="x", padx=12, pady=(0, 10))

        gpu_card = ctk.CTkFrame(cards, fg_color=THEME["inner"], corner_radius=10, border_width=1, border_color=THEME["border"])
        gpu_card.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.gpu_name_label = ctk.CTkLabel(gpu_card, text="🚀 GPU", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
        self.gpu_name_label.pack(fill="x", padx=12, pady=(10, 2))
        self.gpu_value_label = ctk.CTkLabel(gpu_card, text="CPU Mode", text_color=THEME["success"], anchor="w", font=ctk.CTkFont(size=24, weight="bold"))
        self.gpu_value_label.pack(anchor="w", padx=12)
        self.gpu_progress = ctk.CTkProgressBar(gpu_card, progress_color=THEME["success"], fg_color=THEME["input"], height=7)
        self.gpu_progress.set(0)
        self.gpu_progress.pack(fill="x", padx=12, pady=(6, 6))
        self.gpu_detail_label = ctk.CTkLabel(gpu_card, text="VRAM: unavailable", text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=10))
        self.gpu_detail_label.pack(fill="x", padx=12, pady=(0, 10))

        pipeline = ctk.CTkFrame(self.hardware_frame, fg_color=THEME["inner"], corner_radius=10, border_width=1, border_color=THEME["border"])
        pipeline.grid(row=2, column=0, sticky="nsew")
        header = ctk.CTkFrame(pipeline, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(header, text="Transcription Pipeline Tracker", text_color=THEME["text"], font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.hardware_timer_label = ctk.CTkLabel(header, text="Elapsed: 00:00", text_color=THEME["yellow"], font=ctk.CTkFont(size=12, weight="bold"))
        self.hardware_timer_label.pack(side="right")
        self.hardware_cancel_button = self._button(header, "⏹ Cancel", self._cancel, width=88)
        self.hardware_cancel_button.configure(state="disabled", fg_color="#1e1014", hover_color="#dc2626", text_color="#6b3038")
        self.hardware_cancel_button.pack(side="right", padx=(0, 12))

        self.pipeline_stage_definitions = [
            ("1. Media Input", "Validate the selected audio or video file"),
            ("2. Audio Extraction", "FFmpeg normalizes a 16 kHz mono speech stream"),
            ("3. Model & CUDA Load", "Prepare Whisper and move it into accelerator memory"),
            ("4. Whisper Transcription", "Generate speech segments and word-level timestamps"),
            ("5. Timestamp Rendering", "Format the transcript into readable timestamp blocks"),
            ("6. Save & Library", "Write the UTF-8 transcript beside the program"),
        ]
        stages = ctk.CTkFrame(pipeline, fg_color="transparent")
        stages.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.pipeline_stage_widgets = []
        for title, description in self.pipeline_stage_definitions:
            stage = ctk.CTkFrame(stages, fg_color=THEME["input"], corner_radius=8, border_width=1, border_color=THEME["border"], height=48)
            stage.pack(fill="x", pady=2)
            stage.pack_propagate(False)
            dot = ctk.CTkLabel(stage, text="⚪", text_color=THEME["muted"], width=28, font=ctk.CTkFont(size=12))
            dot.pack(side="left", padx=(10, 2))
            info = ctk.CTkFrame(stage, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=4)
            ctk.CTkLabel(info, text=title, text_color=THEME["text"], anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(info, text=description, text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=10)).pack(anchor="w")
            status = ctk.CTkLabel(stage, text="Waiting", text_color=THEME["muted"], width=82, font=ctk.CTkFont(size=10, weight="bold"))
            status.pack(side="right", padx=12)
            self.pipeline_stage_widgets.append({"frame": stage, "dot": dot, "status": status})
    def _show_console(self):
        self._hide_all_views()
        if not hasattr(self, "console_frame"):
            self.console_frame = self._card(self.content, "Console Logs", "Live pipeline output and hardware messages.")
            self.console_frame.grid(row=0, column=0, sticky="nsew")
            full_console_text = ctk.CTkTextbox(self.console_frame, fg_color="#05040d", text_color="#b9f6ff", font=ctk.CTkFont(family="Consolas", size=11))
            full_console_text.pack(fill="both", expand=True, padx=16, pady=(4, 16))
            if self.console_history:
                full_console_text.insert("end", "".join(self.console_history))
                full_console_text.see("end")
            self.console_text_widgets.append(full_console_text)
        self.console_frame.grid()

    def _build_library(self) -> None:
        self.library_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.library_frame.grid_columnconfigure(0, weight=3)
        self.library_frame.grid_columnconfigure(1, weight=2)
        self.library_frame.grid_rowconfigure(0, weight=1)

        list_card = self._card(self.library_frame, "Generated Transcripts", "Files created by JanesCriber in the Transcripts folder.")
        list_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        toolbar = ctk.CTkFrame(list_card, fg_color="transparent")
        toolbar.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(toolbar, text=str(self.paths["transcripts"]), text_color=THEME["muted"], anchor="w", font=ctk.CTkFont(size=10)).pack(side="left", fill="x", expand=True)
        self.library_refresh_button = self._button(toolbar, "↻ Refresh", self._refresh_library, width=92)
        self.library_refresh_button.pack(side="right")
        self.library_scroll = ctk.CTkScrollableFrame(list_card, fg_color=THEME["input"], corner_radius=8, border_width=1, border_color=THEME["border"])
        self.library_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        preview_card = self._card(self.library_frame, "Transcript Viewer", "Select a transcript to read it here without opening Windows Explorer.")
        preview_card.grid(row=0, column=1, sticky="nsew")
        self.preview_title = ctk.CTkLabel(preview_card, text="Nothing selected", text_color=THEME["cyan"], anchor="w", justify="left", wraplength=340, font=ctk.CTkFont(size=12, weight="bold"))
        self.preview_title.pack(fill="x", padx=16, pady=(0, 8))
        self.preview_text = ctk.CTkTextbox(preview_card, fg_color=THEME["input"], text_color=THEME["text"], wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self.preview_text.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.preview_text.tag_config("timestamp", foreground=THEME["magenta"])
        self.preview_text.configure(state="disabled")
        actions = ctk.CTkFrame(preview_card, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 15))
        self.preview_folder_button = self._button(actions, "Open Folder", self._open_selected_folder, width=112)
        self.preview_folder_button.pack(side="left", padx=(0, 6))
        self.preview_delete_button = self._button(actions, "Delete", self._delete_selected_transcript, width=78)
        self.preview_delete_button.configure(hover_color="#991b1b")
        self.preview_delete_button.pack(side="right")
        self._set_preview(None)

    def _refresh_library(self) -> None:
        if not hasattr(self, "library_scroll"):
            return
        for child in self.library_scroll.winfo_children():
            child.destroy()
        entries = discover_transcripts(self.paths["transcripts"])
        if not entries:
            ctk.CTkLabel(self.library_scroll, text="No transcripts yet. Generate one in Transcription Studio.", text_color=THEME["muted"], justify="left").pack(pady=40, padx=20)
            self._set_preview(None)
            return
        if self.selected_transcript and not any(item.path == self.selected_transcript for item in entries):
            self._set_preview(None)
        for entry in entries:
            self._render_transcript_row(entry)

    def _render_transcript_row(self, entry: TranscriptEntry) -> None:
        row = ctk.CTkFrame(self.library_scroll, fg_color=THEME["inner"], corner_radius=7, height=48, border_width=1, border_color=THEME["border"])
        row.pack(fill="x", padx=4, pady=3)
        row.pack_propagate(False)
        tag = ctk.CTkLabel(row, text="TXT", width=48, height=24, corner_radius=4, fg_color=THEME["cyan"], text_color="#ffffff", font=ctk.CTkFont(size=10, weight="bold"))
        tag.pack(side="left", padx=(8, 5))
        folder_button = ctk.CTkButton(row, text="Folder", width=58, height=26, fg_color=THEME["glow"], hover_color=THEME["cyan"], font=ctk.CTkFont(size=10, weight="bold"), command=lambda p=entry.path: self._open_folder_for(p))
        folder_button.pack(side="left", padx=(0, 3))
        delete_button = ctk.CTkButton(row, text="Delete", width=54, height=26, fg_color=THEME["glow"], hover_color="#991b1b", font=ctk.CTkFont(size=10, weight="bold"), command=lambda p=entry.path: self._delete_transcript(p))
        delete_button.pack(side="left", padx=(0, 5))
        title = ctk.CTkLabel(row, text=entry.path.stem, text_color=THEME["text"], anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
        title.pack(side="left", fill="x", expand=True, padx=4)
        size_mb = entry.size / (1024 * 1024)
        ctk.CTkLabel(row, text=f"{size_mb:.1f} MB", text_color=THEME["muted"], width=58, anchor="e", font=ctk.CTkFont(size=10)).pack(side="right", padx=(3, 8))
        for widget in (row, tag, title):
            widget.bind("<Button-1>", lambda _event, p=entry.path: self._select_transcript(p))
        if self.selected_transcript == entry.path:
            row.configure(border_color=THEME["magenta"])

    def _set_preview(self, path: Path | None) -> None:
        self.selected_transcript = path
        if not hasattr(self, "preview_text"):
            return
        if path is None:
            self.preview_title.configure(text="Nothing selected")
            content = "Select a transcript from the library to view its timestamped text here."
            state = "disabled"
        else:
            try:
                content = read_transcript(path, self.paths["transcripts"])
            except (OSError, ValueError) as exc:
                content = f"Could not read this transcript.\n\n{exc}"
            self.preview_title.configure(text=path.name)
            state = "disabled"
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        for line in content.splitlines(keepends=True):
            line_body = line.rstrip("\r\n")
            line_end = line[len(line_body):]
            if re.fullmatch(r"\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]", line_body):
                self.preview_text.insert("end", line_body, "timestamp")
                self.preview_text.insert("end", line_end)
            else:
                self.preview_text.insert("end", line)
        self.preview_text.configure(state=state)
        enabled = "normal" if path is not None else "disabled"
        self.preview_folder_button.configure(state=enabled)
        self.preview_delete_button.configure(state=enabled)

    def _select_transcript(self, path: Path) -> None:
        self._set_preview(path)
        if hasattr(self, "library_scroll"):
            self._refresh_library()

    def _open_folder_for(self, path: Path) -> None:
        if not is_managed_transcript(path, self.paths["transcripts"]):
            return
        try:
            os.startfile(str(path.parent))
        except Exception as exc:
            messagebox.showerror("Could Not Open Folder", str(exc))

    def _open_selected_folder(self) -> None:
        if self.selected_transcript:
            self._open_folder_for(self.selected_transcript)

    def _delete_transcript(self, path: Path) -> None:
        if not is_managed_transcript(path, self.paths["transcripts"]):
            return
        if not messagebox.askyesno("Confirm deletion", f"Delete '{path.name}'?\n\nThis removes the transcript from the JanesCriber library and cannot be undone.", icon="warning"):
            return
        try:
            path.unlink()
            if self.selected_transcript == path:
                self._set_preview(None)
            self._refresh_library()
        except OSError as exc:
            messagebox.showerror("Could Not Delete", f"JanesCriber could not delete this transcript.\n\n{exc}")

    def _delete_selected_transcript(self) -> None:
        if self.selected_transcript:
            self._delete_transcript(self.selected_transcript)

    def _browse(self):
        path = filedialog.askopenfilename(title="Choose audio or video", filetypes=[("Audio and video", "*.*"), ("All files", "*.*")])
        if path:
            self._set_source_path(Path(path), "Browse")

    def _handle_dropped_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        path = paths[0].expanduser()
        if not path.is_file():
            self._log(f"Drag-and-drop ignored; not a file: {path}")
            self.status.configure(text="Drop a file, not a folder.")
            return
        self._set_source_path(path, "Drag-and-drop")
        if len(paths) > 1:
            self._log(f"Drag-and-drop received {len(paths)} files; selected the first one.")

    def _set_source_path(self, path: Path, source: str) -> None:
        path = path.resolve()
        self.source_entry.delete(0, "end")
        self.source_entry.insert(0, str(path))
        self.status.configure(text=f"Ready: {path.name}")
        self._log(f"Media selected by {source.lower()}: {path}")

    def _on_language_menu_select(self, choice: str) -> None:
        if choice == "🌐 Custom Multi-Select...":
            self._open_multi_language_modal()
            return
        codes = LANGUAGE_PRESETS.get(choice, [])
        if isinstance(codes, list):
            self.selected_language_codes = list(codes)
            if hasattr(self, "model_menu"):
                self._sync_vosk_model_for_language(self.model_menu, self.selected_language_codes)
            if hasattr(self, "live_model_menu"):
                self._sync_vosk_model_for_language(self.live_model_menu, self.selected_language_codes)

    def _apply_custom_languages(self, codes: list[str]) -> None:
        self.selected_language_codes = list(codes)
        if hasattr(self, "model_menu"):
            self._sync_vosk_model_for_language(self.model_menu, self.selected_language_codes)
        if hasattr(self, "live_model_menu"):
            self._sync_vosk_model_for_language(self.live_model_menu, self.selected_language_codes)
        if not codes:
            self.language_menu.set("Auto-Detect (Best Available Detection)")
            return
        preset_match = next(
            (name for name, preset_codes in LANGUAGE_PRESETS.items()
             if isinstance(preset_codes, list) and preset_codes and set(preset_codes) == set(codes)),
            None,
        )
        if preset_match:
            self.language_menu.set(preset_match)
            return
        names = [ALL_AVAILABLE_LANGUAGES.get(code, code.upper()).split(" (")[0] for code in codes]
        label = f"Multi ({len(codes)}): {', '.join(names)}"
        values = list(self.language_menu.cget("values"))
        if label not in values:
            values.append(label)
            self.language_menu.configure(values=values)
        self.language_menu.set(label)

    def _open_multi_language_modal(self) -> None:
        modal = ctk.CTkToplevel(self)
        modal.title("Select Spoken Languages - JanesCriber")
        modal.geometry("460x540")
        modal.resizable(False, False)
        modal.configure(fg_color=THEME["bg"])
        modal.transient(self)
        modal.grab_set()
        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 230
            y = self.winfo_y() + (self.winfo_height() // 2) - 270
            modal.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        header = ctk.CTkFrame(modal, fg_color=THEME["card"], corner_radius=0)
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="🔀 Multi-Language Speech Selection", text_color=THEME["text"], font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(
            header,
            text="Select one or more languages spoken in your media.\nWhisper will be primed to recognize mixed speech and code-switching.",
            text_color=THEME["muted"],
            font=ctk.CTkFont(size=11),
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        search_row = ctk.CTkFrame(modal, fg_color="transparent")
        search_row.pack(fill="x", padx=16, pady=(0, 8))
        search_row.grid_columnconfigure(0, weight=1)
        search_var = tk.StringVar(value="")
        search_entry = ctk.CTkEntry(
            search_row,
            textvariable=search_var,
            placeholder_text="Search by language, native name, or code…",
            height=34,
            fg_color=THEME["input"],
            border_color=THEME["border"],
        )
        search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        selected_count = ctk.CTkLabel(search_row, text="0 selected", text_color=THEME["muted"], width=72)
        selected_count.grid(row=0, column=1)

        scroll = ctk.CTkScrollableFrame(modal, fg_color=THEME["inner"], corner_radius=8, border_width=1, border_color=THEME["border"])
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        check_vars: dict[str, ctk.BooleanVar] = {}
        for code in ALL_AVAILABLE_LANGUAGES:
            check_vars[code] = ctk.BooleanVar(value=code in self.selected_language_codes)

        def update_selected_count() -> None:
            count = sum(1 for var in check_vars.values() if var.get())
            selected_count.configure(text=f"{count} selected")

        def render_language_rows(*_args) -> None:
            query = search_var.get().strip().casefold()
            for child in scroll.winfo_children():
                child.destroy()
            matches = [
                (code, label)
                for code, label in ALL_AVAILABLE_LANGUAGES.items()
                if not query or query in f"{label} {code}".casefold()
            ]
            if not matches:
                ctk.CTkLabel(scroll, text="No matching languages.", text_color=THEME["muted"]).pack(anchor="w", padx=12, pady=12)
                return
            for code, label in matches:
                var = check_vars[code]
                ctk.CTkCheckBox(
                    scroll,
                    text=f"{label} ({code.upper()})",
                    variable=var,
                    command=update_selected_count,
                    font=ctk.CTkFont(size=12),
                    text_color=THEME["text"],
                    fg_color=THEME["cyan"],
                    hover_color=THEME["cyan_hover"],
                    border_color=THEME["glow"],
                ).pack(anchor="w", padx=12, pady=6)

        search_var.trace_add("write", render_language_rows)
        render_language_rows()
        update_selected_count()

        buttons = ctk.CTkFrame(modal, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(0, 16))

        def clear_selection() -> None:
            self._apply_custom_languages([])
            modal.destroy()

        def apply_selection() -> None:
            self._apply_custom_languages([code for code, var in check_vars.items() if var.get()])
            modal.destroy()

        ctk.CTkButton(buttons, text="Auto-Detect (Clear)", width=140, height=34, fg_color=THEME["input"], hover_color=THEME["glow"], text_color=THEME["muted"], command=clear_selection).pack(side="left")
        ctk.CTkButton(buttons, text="Apply Selection", width=160, height=34, fg_color=THEME["cyan"], hover_color=THEME["cyan_hover"], font=ctk.CTkFont(weight="bold"), command=apply_selection).pack(side="right")

    def destroy(self):
        if self.live_session and self.live_session.is_running:
            self.live_session.stop(timeout=0.5)
        if self.job_process and self.job_process.is_alive():
            self.cancel_event.set()
            self.job_process.join(timeout=1.0)
            if self.job_process.is_alive():
                self.job_process.terminate()
                self.job_process.join(timeout=1.0)
        if hasattr(self, "file_drop"):
            self.file_drop.disable()
        if hasattr(self, "hw_monitor"):
            self.hw_monitor.stop()
        super().destroy()

    def _log(self, text: str):
        line = text.rstrip() + "\n"
        self.console_history.append(line)
        if len(self.console_history) > 1200:
            del self.console_history[:-1200]
        try:
            with self._diagnostic_log_lock:
                if self._diagnostic_log.exists() and self._diagnostic_log.stat().st_size > 2 * 1024 * 1024:
                    rotated = self._diagnostic_log.with_suffix(".log.1")
                    rotated.unlink(missing_ok=True)
                    self._diagnostic_log.replace(rotated)
                with self._diagnostic_log.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(f"{datetime.now().isoformat(timespec='seconds')} {line}")
        except OSError:
            pass
        self.log_queue.put(line)

    def _drain_logs(self):
        if not self.console_text_widgets:
            self.after(120, self._drain_logs)
            return
        try:
            while True:
                text = self.log_queue.get_nowait()
                for console_text in self.console_text_widgets:
                    console_text.insert("end", text)
                    console_text.see("end")
        except queue.Empty:
            pass
        self.after(120, self._drain_logs)

    def _refresh_hardware(self):
        self.hw_info = detect_hardware()
        if hasattr(self, "hardware_backend_label"):
            source = self.hw_monitor.latest_snapshot.telemetry_source
            self.hardware_backend_label.configure(
                text=f"Backend: {self.hw_info['accelerator']}  •  Device: {self.hw_info['device'].upper()}  •  Telemetry: {source}"
            )
            self._apply_hardware_stats(self.hw_monitor.latest_snapshot)

    def _apply_hardware_stats(self, snapshot: HardwareTelemetrySnapshot) -> None:
        if not snapshot or not self.winfo_exists() or not hasattr(self, "cpu_value_label"):
            return
        self.cpu_value_label.configure(text=f"{snapshot.cpu_system_pct:.1f} %")
        self.cpu_progress.set(max(0.0, min(1.0, snapshot.cpu_system_pct / 100.0)))
        self.cpu_detail_label.configure(
            text=f"System load • App: {snapshot.cpu_app_pct:.1f}% • {self.hw_info['cores']} logical threads"
        )
        self.cpu_name_label.configure(text=f"⚡ {self.hw_info['cpu']}")

        self.ram_value_label.configure(text=f"{snapshot.ram_system_pct:.1f} %")
        self.ram_progress.set(max(0.0, min(1.0, snapshot.ram_system_pct / 100.0)))
        self.ram_name_label.configure(text=f"💾 System RAM ({snapshot.ram_total_gb:.1f} GB)")
        self.ram_detail_label.configure(
            text=f"{snapshot.ram_used_gb:.1f} GB / {snapshot.ram_total_gb:.1f} GB • App: {snapshot.ram_app_mb:.0f} MB"
        )

        has_gpu = bool(snapshot.gpu_name and snapshot.gpu_name != "Not detected")
        if has_gpu:
            self.gpu_name_label.configure(text=f"🚀 {snapshot.gpu_name}")
            self.gpu_value_label.configure(text=f"{snapshot.gpu_system_pct:.0f} %")
            self.gpu_progress.set(max(0.0, min(1.0, snapshot.gpu_system_pct / 100.0)))
            self.gpu_detail_label.configure(
                text=(
                    f"VRAM: {snapshot.gpu_vram_used_mb:,} / {snapshot.gpu_vram_total_mb:,} MB • "
                    f"{snapshot.gpu_temp_c}°C • Workload: {snapshot.gpu_app_pct:.0f}% ({snapshot.gpu_engine_name})"
                )
            )
        else:
            self.gpu_name_label.configure(text="🚀 GPU not detected")
            self.gpu_value_label.configure(text="CPU Mode")
            self.gpu_progress.set(0)
            self.gpu_detail_label.configure(text="Software fallback • GPU telemetry unavailable")

        if self.is_processing and self.start_processing_time:
            elapsed = max(0, int(time.time() - self.start_processing_time))
            self.hardware_timer_label.configure(text=f"Elapsed: {elapsed // 60:02d}:{elapsed % 60:02d}")
        if hasattr(self, "hardware_status_label"):
            live_active = bool(self.live_session and self.live_session.is_running)
            mode = "Transcription active" if self.is_processing or live_active else "Monitoring idle system"
            self.hardware_status_label.configure(
                text=f"● {mode} • Last sample: {time.strftime('%H:%M:%S')} • Source: {snapshot.telemetry_source}"
            )
        self._update_pipeline_stages(self._last_progress if hasattr(self, "_last_progress") else 0.0)

    def _update_pipeline_stages(self, fraction: float) -> None:
        if not hasattr(self, "pipeline_stage_widgets"):
            return
        thresholds = (0.20, 0.30, 0.55, 0.74, 0.85, 1.01)
        active_index = next((i for i, threshold in enumerate(thresholds) if fraction < threshold), len(thresholds) - 1)
        for index, stage in enumerate(self.pipeline_stage_widgets):
            if not self.is_processing and fraction <= 0:
                state = "waiting"
            elif not self.is_processing and fraction >= 1:
                state = "done"
            elif index < active_index:
                state = "done"
            elif index == active_index:
                state = "running"
            else:
                state = "waiting"
            if state == "done":
                stage["dot"].configure(text="✅", text_color=THEME["success"])
                stage["status"].configure(text="Finished" if self.is_processing else "Done", text_color=THEME["success"])
                stage["frame"].configure(fg_color="#091712", border_color="#104230")
            elif state == "running":
                stage["dot"].configure(text="⏳", text_color=THEME["cyan"])
                stage["status"].configure(text="Running...", text_color=THEME["cyan"])
                stage["frame"].configure(fg_color="#0d182b", border_color="#1d3d6b")
            else:
                stage["dot"].configure(text="⚪", text_color=THEME["muted"])
                stage["status"].configure(text="Waiting", text_color=THEME["muted"])
                stage["frame"].configure(fg_color=THEME["input"], border_color=THEME["border"])

    def _start(self):
        source = self.source_entry.get().strip()
        if not source:
            messagebox.showwarning("Choose media", "Select an audio or video file first.")
            return
        if not Path(source).is_file():
            messagebox.showerror("File not found", "That media file no longer exists.")
            return
        if self.worker and self.worker.is_alive():
            return
        self.cancel_event = self.mp_context.Event()
        self.is_processing = True
        self.start_processing_time = time.time()
        self._last_progress = 0.01
        self.hw_monitor.set_processing(True)
        self._update_pipeline_stages(self._last_progress)
        if hasattr(self, "hardware_cancel_button"):
            self.hardware_cancel_button.configure(state="normal", fg_color="#7f1d1d", hover_color="#dc2626", text_color="#ffffff")
        self._log("=" * 68)
        self._log(f"Transcription requested: {Path(source).resolve()}")
        engine = self._engine_id(self.engine_menu)
        model = self._model_id(self.model_menu)
        self._log(f"ASR engine: {engine} | Model: {model} | Language: {self.language_menu.get()}")
        self._log(f"Transcript cache: {'enabled' if self.cache.get() else 'disabled'} | Output: {self.paths['transcripts']}")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.sidebar_status.configure(text="● TRANSCRIBING", text_color=THEME["yellow"])
        language = ",".join(self.selected_language_codes) or None

        self.job_events = self.mp_context.Queue(maxsize=512)
        self.job_process = self.mp_context.Process(
            target=run_transcription_job,
            kwargs={
                "source": source,
                "engine": engine,
                "model_name": model,
                "language": language,
                "paths": self.paths,
                "overwrite": bool(self.overwrite.get()),
                "use_cache": bool(self.cache.get()),
                "event_queue": self.job_events,
                "cancel": self.cancel_event,
            },
            name="JanesCriberWhisperWorker",
        )
        self.job_process.start()
        self.worker = threading.Thread(
            target=self._monitor_job_process,
            args=(self.job_process, self.job_events),
            daemon=True,
            name="JanesCriberJobMonitor",
        )
        self.worker.start()

    def _monitor_job_process(self, process, events) -> None:
        terminal = False

        def handle(event) -> None:
            nonlocal terminal
            if not event:
                return
            kind = event[0]
            if kind == "log":
                self._log(str(event[1]))
            elif kind == "progress":
                post_to_tk(self, lambda value=event[1], text=event[2]: self._apply_progress(value, text))
            elif kind == "completed":
                terminal = True
                output = Path(str(event[1]))
                self.last_output = output
                post_to_tk(self, lambda result=output: self._finished(result))
            elif kind == "cancelled":
                terminal = True
                post_to_tk(self, self._cancelled)
            elif kind == "error":
                terminal = True
                post_to_tk(self, lambda message=str(event[1]): self._failed(RuntimeError(message)))

        try:
            while process.is_alive():
                try:
                    handle(events.get(timeout=0.2))
                except queue.Empty:
                    pass
            process.join(timeout=1.0)
            while True:
                try:
                    handle(events.get_nowait())
                except queue.Empty:
                    break
            if not terminal and process.exitcode not in (0, None):
                post_to_tk(self, lambda: self._failed(RuntimeError("The transcription worker exited unexpectedly.")))
            elif not terminal:
                post_to_tk(self, lambda: self._failed(RuntimeError("The transcription worker ended without a result.")))
        finally:
            self.job_process = None
            try:
                events.close()
                events.join_thread()
            except (AttributeError, OSError):
                pass

    def _progress(self, fraction: float, message: str):
        self._log(message)
        post_to_tk(self, lambda value=fraction, text=message: self._apply_progress(value, text))

    def _apply_progress(self, fraction: float, message: str) -> None:
        self._last_progress = fraction
        self.progress.set(fraction)
        self.status.configure(text=message)
        self._update_pipeline_stages(fraction)

    def _finished(self, output: Path):
        self.is_processing = False
        self.hw_monitor.set_processing(False)
        self._last_progress = 1.0
        self._update_pipeline_stages(1.0)
        self._log(f"[+] Completed successfully: {output}")
        self.progress.set(1)
        self.status.configure(text="Transcript generated successfully.", text_color=THEME["success"])
        self.output_label.configure(text=f"Saved transcript in Transcripts:\n{output}\n\nOpen it with any text editor. The source file was not moved or modified.", text_color=THEME["success"])
        if hasattr(self, "library_scroll"):
            self._refresh_library()
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        if hasattr(self, "hardware_cancel_button"):
            self.hardware_cancel_button.configure(state="disabled", fg_color="#1e1014", text_color="#6b3038")
        self.sidebar_status.configure(text="● READY", text_color=THEME["success"])

    def _failed(self, exc: BaseException):
        self.is_processing = False
        self.hw_monitor.set_processing(False)
        self._update_pipeline_stages(0.0)
        self._log(f"[!] {exc}")
        self.status.configure(text=f"Could not complete: {exc}", text_color="#f87171")
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        if hasattr(self, "hardware_cancel_button"):
            self.hardware_cancel_button.configure(state="disabled", fg_color="#1e1014", text_color="#6b3038")
        self.sidebar_status.configure(text="● READY", text_color=THEME["success"])

    def _cancelled(self):
        self.is_processing = False
        self.hw_monitor.set_processing(False)
        self._update_pipeline_stages(0.0)
        self._log("[!] Transcription cancelled by user.")
        self.status.configure(text="Transcription cancelled.", text_color=THEME["yellow"])
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        if hasattr(self, "hardware_cancel_button"):
            self.hardware_cancel_button.configure(state="disabled", fg_color="#1e1014", text_color="#6b3038")
        self.sidebar_status.configure(text="● READY", text_color=THEME["success"])

    def _cancel(self):
        if not (self.worker and self.worker.is_alive() and self.job_process and self.job_process.is_alive()):
            return
        self.cancel_event.set()
        self.status.configure(text="Cancellation requested…", text_color=THEME["yellow"])


def launch() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    JanesCriberApp().mainloop()
