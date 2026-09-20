"""Near-real-time transcription from microphones, system output, or an app."""

from __future__ import annotations

import json
import os
import multiprocessing
import queue
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from .cancellation import PipelineAborted
from .formatting import timestamp
from .hardware import clear_accelerator_cache, detect_hardware
from .languages import build_multilingual_prompt, normalize_language_codes
from .model_manager import ensure_model_downloaded, load_whisper_model
from .pipeline_config import SUPPORTED_ENGINES, SUPPORTED_MODELS
from .vosk_backend import VOSK_MODEL_SPECS, default_model_for_language, ensure_vosk_model
from .wav2vec_backend import WAV2VEC2_MODEL_SPECS, load_wav2vec2_session
from .qwen_backend import QWEN_MODEL_SPECS


class _NullWriter:
    """File-like sink for GUI workers that do not have stdout/stderr."""

    def write(self, value: str) -> int:
        return len(value) if value else 0

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


def _ensure_worker_streams() -> None:
    """Keep third-party progress writers safe under pythonw/PyInstaller."""
    if sys.stdout is None:
        sys.stdout = _NullWriter()
    if sys.stderr is None:
        sys.stderr = _NullWriter()


@dataclass(frozen=True)
class LiveTranscriptionConfig:
    """Settings for live capture and rolling local ASR recognition."""

    engine: str = "whisper"
    model_name: str = "tiny"
    language: tuple[str, ...] = ()
    sample_rate: int = 16000
    block_seconds: float = 0.5
    window_seconds: float = 8.0
    hop_seconds: float = 2.5

    def __post_init__(self) -> None:
        engine = str(self.engine).strip().lower()
        if engine not in SUPPORTED_ENGINES:
            raise ValueError(f"Unsupported ASR engine '{self.engine}'.")
        object.__setattr__(self, "engine", engine)
        model = str(self.model_name).strip().lower()
        languages = tuple(normalize_language_codes(self.language))
        if engine == "whisper":
            if model not in SUPPORTED_MODELS:
                raise ValueError(f"Unsupported Whisper model '{self.model_name}'.")
        elif engine == "vosk":
            if model in {"", "auto", "turbo"}:
                model = default_model_for_language(languages[0] if languages else "en")
            if model not in VOSK_MODEL_SPECS:
                raise ValueError(f"Unsupported Vosk model '{self.model_name}'.")
            if len(languages) > 1:
                raise ValueError("Vosk / Kaldi uses one language model at a time. Choose one spoken language.")
            if len(languages) == 1 and VOSK_MODEL_SPECS[model].language != languages[0]:
                raise ValueError(
                    f"Vosk model '{model}' is for {VOSK_MODEL_SPECS[model].language}, "
                    f"but the selected language is {languages[0]}. Choose a matching model."
                )
            if not languages:
                languages = (VOSK_MODEL_SPECS[model].language,)
        elif engine == "wav2vec2":
            if model in {"", "auto", "turbo"}:
                model = "wav2vec2-base-960h"
            if model not in WAV2VEC2_MODEL_SPECS:
                raise ValueError(f"Unsupported Wav2Vec2 model '{self.model_name}'.")
            if languages and languages != ("en",):
                raise ValueError("Wav2Vec2 currently supports English only. Choose English or use Whisper/Vosk.")
            languages = ("en",)
        else:
            raise ValueError("Qwen3-ASR is currently available for file transcription only. Use Whisper, Vosk, or Wav2Vec2 for live sessions.")
        object.__setattr__(self, "model_name", model)
        if self.sample_rate < 8000:
            raise ValueError("Live capture sample rate is too low.")
        if self.block_seconds <= 0 or self.window_seconds <= 0 or self.hop_seconds <= 0:
            raise ValueError("Live capture timing values must be positive.")
        if self.hop_seconds > self.window_seconds:
            raise ValueError("Live transcription hop cannot exceed its window.")
        object.__setattr__(self, "language", languages)


@dataclass(frozen=True)
class LiveSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class CaptureSource:
    """A user-selectable live audio source."""

    kind: Literal["microphone", "system", "application"]
    label: str
    identifier: str | None = None
    pid: int | None = None


def list_microphone_sources() -> list[CaptureSource]:
    """Return physical and virtual microphone choices."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
    except Exception:
        return []
    sources: list[CaptureSource] = []
    names: set[str] = set()
    for device in devices:
        if isinstance(device, dict) and int(device.get("max_input_channels", 0)) > 0:
            name = str(device.get("name", "Microphone")).strip()
            if name and name not in names:
                names.add(name)
                sources.append(CaptureSource("microphone", name, identifier=name))
    return sources


def list_input_devices() -> list[str]:
    """Backward-compatible list of microphone names."""
    return [source.label for source in list_microphone_sources()]


def list_system_output_sources() -> list[CaptureSource]:
    """Return WASAPI loopback sources for the available speaker endpoints."""
    try:
        import soundcard as sc
        microphones = sc.all_microphones(include_loopback=True)
    except Exception:
        return []
    sources: list[CaptureSource] = []
    seen: set[str] = set()
    for microphone in microphones:
        if not bool(getattr(microphone, "isloopback", False)):
            continue
        name = str(getattr(microphone, "name", "System output")).strip()
        if name and name not in seen:
            seen.add(name)
            sources.append(CaptureSource("system", f"{name} (system output)", identifier=name))
    return sources


def _friendly_application_name(process_name: str) -> str:
    known_names = {
        "msedge.exe": "Microsoft Edge",
        "chrome.exe": "Google Chrome",
        "firefox.exe": "Mozilla Firefox",
        "discord.exe": "Discord",
        "whatsapp.exe": "WhatsApp",
        "spotify.exe": "Spotify",
        "code.exe": "Visual Studio Code",
        "explorer.exe": "File Explorer",
    }
    normalized = process_name.casefold()
    if normalized in known_names:
        return known_names[normalized]
    stem = Path(process_name).stem or process_name
    return re.sub(r"(?<!^)(?=[A-Z])", " ", stem).strip() or "Application"


def _format_application_label(process_name: str, window_title: str) -> str:
    app_name = _friendly_application_name(process_name)
    title = " ".join(window_title.split())
    return f"{app_name} — {title}" if title and title.casefold() != app_name.casefold() else app_name


def _list_visible_windows() -> list[tuple[int, str, str]]:
    """Return visible top-level Windows apps as (pid, process, window title)."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes
        import psutil
    except ImportError:
        return []

    user32 = ctypes.windll.user32
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
    user32.GetWindow.restype = wintypes.HWND

    windows: list[tuple[int, str, str]] = []
    seen_pids: set[int] = set()
    owner_flag = 4  # GW_OWNER: ignore owned popups and keep one card per app.
    ignored = {
        "applicationframehost.exe",
        "dwm.exe",
        "lockapp.exe",
        "searchhost.exe",
        "shellexperiencehost.exe",
        "startmenuexperiencehost.exe",
        "textinputhost.exe",
        "widgetservice.exe",
        "widgets.exe",
    }

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, owner_flag):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True
        pid_value = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
        pid = int(pid_value.value)
        if pid <= 4 or pid in seen_pids:
            return True
        try:
            process_name = str(psutil.Process(pid).name() or "").strip()
        except (psutil.Error, OSError):
            return True
        if not process_name or process_name.casefold() in ignored:
            return True
        seen_pids.add(pid)
        windows.append((pid, process_name, title))
        return True

    user32.EnumWindows(callback, 0)
    return windows


def list_application_sources() -> list[CaptureSource]:
    """Return friendly cards for visible application windows.

    PIDs are deliberately kept out of the UI. They remain internal metadata
    used by the Windows process-loopback backend after the user picks an app.
    """
    sources = [
        CaptureSource("application", _format_application_label(name, title), identifier=name, pid=pid)
        for pid, name, title in _list_visible_windows()
    ]
    return sorted(sources, key=lambda source: source.label.casefold())


class LiveTranscriber:
    """Capture live audio and publish timestamped transcript updates."""

    def __init__(
        self,
        paths: dict[str, Path],
        config: LiveTranscriptionConfig,
        *,
        capture_source: CaptureSource | None = None,
        device_name: str | None = None,
        on_status: Callable[[str], None] | None = None,
        on_text: Callable[[str, list[LiveSegment]], None] | None = None,
        on_finished: Callable[[Path], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        self.paths = paths
        self.config = config
        self.capture_source = capture_source or CaptureSource(
            "microphone", device_name or "Default microphone", identifier=device_name
        )
        self.device_name = device_name  # compatibility for callers from older builds
        self.on_status = on_status
        self.on_text = on_text
        self.on_finished = on_finished
        self.on_error = on_error
        self._stop_event = threading.Event()
        self._audio_queue: queue.Queue[Any] = queue.Queue(maxsize=64)
        self._thread: threading.Thread | None = None
        self._stream: Any = None
        self._capture_thread: threading.Thread | None = None
        self._capture_error: BaseException | None = None
        self._segments: list[LiveSegment] = []
        self._segment_keys: set[tuple[int, int, str]] = set()
        self._output_path: Path | None = None
        self._started_at = ""
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def output_path(self) -> Path | None:
        return self._output_path

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._segments.clear()
        self._segment_keys.clear()
        self._capture_error = None
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        self._started_at = stamp
        self._output_path = self._next_output_path(stamp)
        self._thread = threading.Thread(target=self._run, daemon=True, name="JanesCriberLiveTranscription")
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        stream = self._stream
        if stream is not None:
            try:
                if self.capture_source.kind == "application":
                    stream.stop()
                    stream.close()
                elif self.capture_source.kind == "microphone":
                    stream.stop()
                    stream.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(0.1, timeout))

    def _run(self) -> None:
        try:
            import numpy as np
        except ImportError as exc:
            self._fail(RuntimeError("Live transcription needs its audio and AI packages. Run setup.bat again."))
            return

        try:
            if self.config.engine == "vosk":
                self._run_vosk(np)
                return
            if self.config.engine == "wav2vec2":
                self._run_wav2vec2(np)
                return
            try:
                import whisper
                import torch
            except ImportError as exc:
                raise RuntimeError("Live Whisper transcription needs its AI packages. Run setup.bat again.") from exc
            hardware = detect_hardware()
            self._emit_status("Loading the live Whisper model...")
            ensure_model_downloaded(
                whisper, self.config.model_name, self.paths["model_cache"], self._progress, self._stop_event
            )
            device = str(hardware["device"])
            try:
                model = load_whisper_model(
                    whisper,
                    self.config.model_name,
                    self.paths["model_cache"],
                    device,
                    torch_module=torch,
                    progress=self._progress,
                    cancel=self._stop_event,
                )
            except PipelineAborted:
                raise
            except Exception as exc:
                if device == "cpu":
                    raise RuntimeError(f"Whisper could not load for live transcription: {exc}") from exc
                self._emit_status(f"GPU load was unavailable ({exc}); retrying live mode on CPU...")
                clear_accelerator_cache(torch, device)
                device = "cpu"
                model = load_whisper_model(
                    whisper,
                    self.config.model_name,
                    self.paths["model_cache"],
                    device,
                    torch_module=torch,
                    progress=self._progress,
                    cancel=self._stop_event,
                )
            language = list(self.config.language)
            primary, prompt = build_multilingual_prompt(language)
            options: dict[str, Any] = {
                "word_timestamps": False,
                "fp16": device == "cuda",
                "temperature": 0.0,
                "condition_on_previous_text": False,
                "verbose": False,
            }
            if primary:
                options["language"] = primary
            if prompt:
                options["initial_prompt"] = prompt

            self._start_capture(np)
            self._emit_status(f"Listening from {self.capture_source.label}. Speak normally; new transcript lines will appear below.")

            chunks: list[Any] = []
            buffered_samples = 0
            total_samples = 0
            next_pass = time.monotonic() + min(1.5, self.config.hop_seconds)
            while not self._stop_event.is_set():
                try:
                    chunk = self._audio_queue.get(timeout=0.25)
                except queue.Empty:
                    if self._capture_error is not None:
                        raise RuntimeError(f"Audio capture stopped: {self._capture_error}") from self._capture_error
                    continue
                chunks.append(chunk)
                buffered_samples += len(chunk)
                total_samples += len(chunk)
                max_samples = round(self.config.window_seconds * self.config.sample_rate)
                while buffered_samples > max_samples and chunks:
                    removed = chunks.pop(0)
                    buffered_samples -= len(removed)
                if buffered_samples < round(1.5 * self.config.sample_rate) or time.monotonic() < next_pass:
                    continue
                audio = np.concatenate(chunks).astype(np.float32, copy=False)
                window_start = max(0.0, (total_samples - len(audio)) / self.config.sample_rate)
                self._recognize(model, audio, window_start, options)
                next_pass = time.monotonic() + self.config.hop_seconds

            if chunks and buffered_samples >= round(0.4 * self.config.sample_rate):
                audio = np.concatenate(chunks).astype(np.float32, copy=False)
                window_start = max(0.0, (total_samples - len(audio)) / self.config.sample_rate)
                self._recognize(model, audio, window_start, options)
            if self._capture_error is not None and not self._stop_event.is_set():
                raise RuntimeError(f"Audio capture stopped: {self._capture_error}") from self._capture_error
            self._publish()
            self._emit_finished()
        except PipelineAborted:
            self._publish()
            self._emit_finished()
        except Exception as exc:
            self._fail(RuntimeError(f"Live transcription stopped: {exc}"))
        finally:
            stream = self._stream
            self._stream = None
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            if self._capture_thread and self._capture_thread.is_alive():
                self._capture_thread.join(timeout=1.0)
            self._capture_thread = None

    def _run_vosk(self, np: Any) -> None:
        """Run lightweight streaming recognition without importing Whisper or Torch."""
        try:
            import vosk
        except ImportError as exc:
            raise RuntimeError("Live Vosk transcription needs the Vosk package. Run setup.bat again.") from exc

        self._emit_status(f"Loading Vosk / Kaldi model: {self.config.model_name}…")
        model_path = ensure_vosk_model(
            self.config.model_name,
            self.paths["vosk_model_cache"],
            self._progress,
            self._stop_event,
        )
        try:
            vosk.SetLogLevel(-1)
        except AttributeError:
            pass
        model = vosk.Model(str(model_path))
        recognizer = vosk.KaldiRecognizer(model, self.config.sample_rate)
        recognizer.SetWords(True)
        self._start_capture(np)
        self._emit_status(
            f"Listening from {self.capture_source.label} with Vosk / Kaldi. Speak normally; new transcript lines will appear below."
        )
        while not self._stop_event.is_set():
            try:
                chunk = self._audio_queue.get(timeout=0.25)
            except queue.Empty:
                if self._capture_error is not None:
                    raise RuntimeError(f"Audio capture stopped: {self._capture_error}") from self._capture_error
                continue
            samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
            if not len(samples):
                continue
            pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
            if recognizer.AcceptWaveform(pcm):
                self._append_vosk_result(json.loads(recognizer.Result() or "{}"))
        final_payload = json.loads(recognizer.FinalResult() or "{}")
        self._append_vosk_result(final_payload)
        if self._capture_error is not None and not self._stop_event.is_set():
            raise RuntimeError(f"Audio capture stopped: {self._capture_error}") from self._capture_error
        self._publish()
        self._emit_finished()

    def _append_vosk_result(self, payload: dict[str, Any]) -> None:
        text = " ".join(str(payload.get("text", "")).split())
        words = payload.get("result", []) or []
        valid_words: list[tuple[float, float]] = []
        for word in words:
            if not isinstance(word, dict):
                continue
            try:
                start = float(word.get("start", 0.0))
                end = max(start, float(word.get("end", start)))
            except (TypeError, ValueError):
                continue
            valid_words.append((start, end))
        if not text and words:
            text = " ".join(str(word.get("word", "")).strip() for word in words if isinstance(word, dict)).strip()
        if not text:
            return
        start = valid_words[0][0] if valid_words else 0.0
        end = valid_words[-1][1] if valid_words else start
        key = (round(start * 10), round(end * 10), text)
        with self._lock:
            if key in self._segment_keys:
                return
            self._segment_keys.add(key)
            self._segments.append(LiveSegment(start, max(start, end), text))
            self._segments.sort(key=lambda item: (item.start, item.end))
            segments = list(self._segments)
        self._publish()
        if self.on_text:
            self.on_text(self._render(segments), segments)

    def _run_wav2vec2(self, np: Any) -> None:
        """Run rolling local Wav2Vec2 recognition using the best local device."""
        hardware = detect_hardware()
        self._emit_status("Loading Wav2Vec2 model for live transcription…")
        session = load_wav2vec2_session(
            self.config.model_name,
            self.paths["wav2vec_model_cache"],
            str(hardware["device"]),
            self._progress,
            self._stop_event,
        )
        self._start_capture(np)
        self._emit_status(
            f"Listening from {self.capture_source.label} with Wav2Vec2 on {session.device.upper()}."
        )
        chunks: list[Any] = []
        buffered_samples = 0
        total_samples = 0
        next_pass = time.monotonic() + min(1.5, self.config.hop_seconds)
        while not self._stop_event.is_set():
            try:
                chunk = self._audio_queue.get(timeout=0.25)
            except queue.Empty:
                if self._capture_error is not None:
                    raise RuntimeError(f"Audio capture stopped: {self._capture_error}") from self._capture_error
                continue
            chunks.append(chunk)
            buffered_samples += len(chunk)
            total_samples += len(chunk)
            max_samples = round(self.config.window_seconds * self.config.sample_rate)
            while buffered_samples > max_samples and chunks:
                buffered_samples -= len(chunks.pop(0))
            if buffered_samples < round(1.5 * self.config.sample_rate) or time.monotonic() < next_pass:
                continue
            audio = np.concatenate(chunks).astype(np.float32, copy=False)
            window_start = max(0.0, (total_samples - len(audio)) / self.config.sample_rate)
            self._recognize_wav2vec2(session, audio, window_start)
            next_pass = time.monotonic() + self.config.hop_seconds
        if chunks and buffered_samples >= round(0.4 * self.config.sample_rate):
            audio = np.concatenate(chunks).astype(np.float32, copy=False)
            window_start = max(0.0, (total_samples - len(audio)) / self.config.sample_rate)
            self._recognize_wav2vec2(session, audio, window_start)
        if self._capture_error is not None and not self._stop_event.is_set():
            raise RuntimeError(f"Audio capture stopped: {self._capture_error}") from self._capture_error
        self._publish()
        self._emit_finished()

    def _recognize_wav2vec2(self, session: Any, audio: Any, window_start: float) -> None:
        if self._stop_event.is_set():
            return
        self._emit_status(
            f"Wav2Vec2 is analyzing the latest {len(audio) / self.config.sample_rate:.1f}s of speech…"
        )
        result = session.transcribe_samples(audio, sample_rate=self.config.sample_rate, offset=window_start)
        for raw in result.get("segments", []) if isinstance(result, dict) else []:
            text = " ".join(str(raw.get("text", "")).split())
            if not text:
                continue
            start = float(raw.get("start", window_start))
            end = max(start, float(raw.get("end", start)))
            with self._lock:
                duplicate = any(
                    item.text == text and abs(item.start - start) < 1.0
                    for item in self._segments
                )
                if duplicate:
                    continue
                self._segments.append(LiveSegment(start, end, text))
                self._segments.sort(key=lambda item: (item.start, item.end))
                segments = list(self._segments)
            self._publish()
            if self.on_text:
                self.on_text(self._render(segments), segments)

    def _start_capture(self, np: Any) -> None:
        blocksize = max(1, round(self.config.sample_rate * self.config.block_seconds))
        if self.capture_source.kind == "microphone":
            import sounddevice as sd
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
                device=self.capture_source.identifier or None,
                callback=self._audio_callback,
            )
            self._stream.start()
            return
        if self.capture_source.kind == "system":
            self._start_system_capture(np, blocksize)
            return
        if self.capture_source.kind == "application":
            self._start_application_capture()
            return
        raise RuntimeError(f"Unknown live capture source: {self.capture_source.kind}")

    def _start_system_capture(self, np: Any, blocksize: int) -> None:
        try:
            import soundcard as sc
        except ImportError as exc:
            raise RuntimeError("System output capture needs the SoundCard package. Run setup.bat again.") from exc
        identifier = self.capture_source.identifier
        if not identifier:
            try:
                identifier = str(sc.default_speaker().name)
            except Exception as exc:
                raise RuntimeError("No system output device is available for loopback capture.") from exc
        try:
            microphone = sc.get_microphone(identifier, include_loopback=True)
        except Exception as exc:
            raise RuntimeError(f"Could not open system output '{self.capture_source.label}': {exc}") from exc

        def capture() -> None:
            try:
                with microphone.recorder(
                    samplerate=self.config.sample_rate,
                    channels=2,
                    blocksize=blocksize,
                ) as recorder:
                    self._stream = recorder
                    while not self._stop_event.is_set():
                        data = recorder.record(numframes=blocksize)
                        self._enqueue_array(np, data, self.config.sample_rate)
            except BaseException as exc:
                if not self._stop_event.is_set():
                    self._capture_error = exc
                    self._stop_event.set()

        self._capture_thread = threading.Thread(target=capture, daemon=True, name="JanesCriberSystemAudioCapture")
        self._capture_thread.start()

    def _start_application_capture(self) -> None:
        if self.capture_source.pid is None:
            raise RuntimeError("Choose an application before starting live transcription.")
        try:
            from proctap import ProcessAudioCapture
        except ImportError as exc:
            raise RuntimeError("Application output capture needs the ProcTap package. Run setup.bat again.") from exc
        try:
            # ProcTap 1.1.x exposes ProcessAudioCapture directly. It always
            # delivers 48 kHz stereo float32 PCM, so the callback can feed the
            # same resampling queue used by the microphone and system paths.
            self._stream = ProcessAudioCapture(
                pid=int(self.capture_source.pid),
                on_data=self._application_audio_callback,
            )
            self._stream.start()
        except BaseException as exc:
            self._stream = None
            raise RuntimeError(f"Could not capture {self.capture_source.label}: {exc}") from exc

    def _application_audio_callback(self, pcm: bytes, frames: int = 0) -> None:
        try:
            import numpy as np
            samples = np.frombuffer(pcm, dtype=np.float32)
            if not len(samples):
                return
            self._enqueue_array(np, samples.reshape(-1, 2), 48000)
        except (TypeError, ValueError):
            try:
                import numpy as np
                samples = np.frombuffer(pcm, dtype=np.int16)
                self._enqueue_array(np, samples.reshape(-1, 2), 48000)
            except (TypeError, ValueError) as exc:
                self._capture_error = exc

    def _enqueue_array(self, np: Any, data: Any, source_rate: int) -> None:
        samples = np.asarray(data, dtype=np.float32)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        samples = samples.reshape(-1)
        if source_rate != self.config.sample_rate and len(samples) > 1:
            target_length = max(1, round(len(samples) * self.config.sample_rate / source_rate))
            positions = np.linspace(0, len(samples) - 1, target_length)
            samples = np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)
        try:
            self._audio_queue.put_nowait(samples)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(samples)
            except queue.Empty:
                pass

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            self._emit_status(f"Audio notice: {status}")
        try:
            chunk = indata[:, 0].copy()
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(indata[:, 0].copy())
            except queue.Empty:
                pass

    def _recognize(self, model: Any, audio: Any, window_start: float, options: dict[str, Any]) -> None:
        if self._stop_event.is_set():
            return
        self._emit_status(f"Listening… analyzing the latest {len(audio) / self.config.sample_rate:.1f}s of speech.")
        result = model.transcribe(audio, **options)
        for raw in result.get("segments", []) if isinstance(result, dict) else []:
            text = " ".join(str(raw.get("text", "")).split())
            if not text:
                continue
            start = window_start + float(raw.get("start", 0.0))
            end = window_start + float(raw.get("end", start - window_start))
            key = (round(start * 10), round(end * 10), text)
            with self._lock:
                if key in self._segment_keys:
                    continue
                self._segment_keys.add(key)
                self._segments.append(LiveSegment(start, max(start, end), text))
                self._segments.sort(key=lambda item: (item.start, item.end))
                segments = list(self._segments)
            self._publish()
            if self.on_text:
                self.on_text(self._render(segments), segments)

    def _render(self, segments: list[LiveSegment] | None = None) -> str:
        items = segments if segments is not None else list(self._segments)
        lines = [
            "JANESCRIBER LIVE TRANSCRIPT",
            f"Started: {self._started_at}",
            f"Engine: {self.config.engine}",
            f"Model: {self.config.model_name}",
            f"Language: {','.join(self.config.language) or 'Auto-detected'}",
            f"Source: {self.capture_source.label}",
            "",
        ]
        for segment in items:
            lines.extend([
                f"[{timestamp(segment.start)} --> {timestamp(segment.end)}]",
                "",
                f">{segment.text}",
                "",
            ])
        if not items:
            lines.append("Listening for speech…")
        return "\n".join(lines) + "\n"

    def _publish(self) -> None:
        if self._output_path is None:
            return
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".live-transcript-", suffix=".tmp", dir=self._output_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(self._render())
                handle.flush()
            Path(temp_name).replace(self._output_path)
        except BaseException:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass

    def _next_output_path(self, stamp: str) -> Path:
        base = Path(self.paths["transcripts"]) / f"Live Transcript {stamp}.txt"
        candidate = base
        index = 2
        while candidate.exists():
            candidate = base.with_name(f"{base.stem} ({index}){base.suffix}")
            index += 1
        return candidate

    def _emit_status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _progress(self, fraction: float, message: str) -> None:
        self._emit_status(message)

    def _emit_finished(self) -> None:
        if self.on_finished and self._output_path:
            self.on_finished(self._output_path)

    def _fail(self, error: BaseException) -> None:
        self._publish()
        if self.on_error:
            self.on_error(error)


def _run_live_process(
    paths: dict[str, Path],
    config: LiveTranscriptionConfig,
    capture_source: CaptureSource,
    event_queue: Any,
    cancel: Any,
) -> None:
    """Host a live session outside the GUI so its model memory is reclaimable."""
    _ensure_worker_streams()

    def emit(kind: str, value: Any = "") -> None:
        try:
            event_queue.put((kind, value))
        except (BrokenPipeError, EOFError, OSError):
            cancel.set()

    try:
        emit("status", f"Live worker started. Preparing {config.engine.title()}…")
        session = LiveTranscriber(
            paths,
            config,
            capture_source=capture_source,
            on_status=lambda message: emit("status", message),
            on_text=lambda text, _segments: emit("text", text),
            on_finished=lambda path: emit("finished", str(path) if path else ""),
            on_error=lambda error: emit("error", str(error)),
        )
        session.start()
        # Publish the output path before model loading completes so the parent
        # can surface a partial transcript after a forced stop.
        emit("started", str(session.output_path) if session.output_path else "")
        while session.is_running:
            if cancel.is_set():
                session.stop(timeout=2.0)
                break
            time.sleep(0.1)
    except BaseException as exc:
        emit("error", f"Live worker could not start: {exc}")


class LiveProcessController:
    """Parent-process controller for an isolated live transcription session."""

    def __init__(
        self,
        paths: dict[str, Path],
        config: LiveTranscriptionConfig,
        *,
        capture_source: CaptureSource,
        on_status: Callable[[str], None] | None = None,
        on_text: Callable[[str, list[LiveSegment]], None] | None = None,
        on_finished: Callable[[Path | None], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        self.paths = paths
        self.config = config
        self.capture_source = capture_source
        self.on_status = on_status
        self.on_text = on_text
        self.on_finished = on_finished
        self.on_error = on_error
        self.output_path: Path | None = None
        self._context = multiprocessing.get_context("spawn")
        self._cancel = self._context.Event()
        self._events = self._context.Queue(maxsize=256)
        self._process: multiprocessing.Process | None = None
        self._monitor: threading.Thread | None = None
        self._terminal = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return bool(self._process and self._process.is_alive() and not self._terminal)

    def start(self) -> None:
        if self.is_running:
            return
        self._cancel.clear()
        self._terminal = False
        self._process = self._context.Process(
            target=_run_live_process,
            kwargs={
                "paths": self.paths,
                "config": self.config,
                "capture_source": self.capture_source,
                "event_queue": self._events,
                "cancel": self._cancel,
            },
            name="JanesCriberLiveWorker",
        )
        self._process.start()
        self._monitor = threading.Thread(target=self._monitor_events, daemon=True, name="JanesCriberLiveMonitor")
        self._monitor.start()

    def stop(self, timeout: float = 2.0) -> None:
        process = self._process
        if process is None:
            return
        self._cancel.set()
        process.join(timeout=max(0.1, timeout))
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        if self._monitor and self._monitor.is_alive() and threading.current_thread() is not self._monitor:
            self._monitor.join(timeout=1.0)
        if not self._terminal:
            partial = self.output_path if self.output_path and self.output_path.is_file() else None
            self._finish(partial)

    def _finish(self, path: Path | None) -> None:
        with self._lock:
            if self._terminal:
                return
            self._terminal = True
            resolved_path = path or self.output_path
            self.output_path = resolved_path
        if self.on_finished:
            self.on_finished(resolved_path)

    def _fail(self, message: str) -> None:
        with self._lock:
            if self._terminal:
                return
            self._terminal = True
        if self.on_error:
            self.on_error(RuntimeError(message))

    def _handle_event(self, event: Any) -> None:
        if not event:
            return
        kind, value = event[0], event[1] if len(event) > 1 else ""
        if kind == "status" and self.on_status:
            self.on_status(str(value))
        elif kind == "started":
            if value:
                self.output_path = Path(str(value))
        elif kind == "text" and self.on_text:
            self.on_text(str(value), [])
        elif kind == "finished":
            self._finish(Path(str(value)) if value else None)
        elif kind == "error":
            self._fail(str(value))

    def _monitor_events(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            while process.is_alive():
                try:
                    self._handle_event(self._events.get(timeout=0.2))
                except queue.Empty:
                    pass
            process.join(timeout=1.0)
            while True:
                try:
                    self._handle_event(self._events.get_nowait())
                except queue.Empty:
                    break
            if not self._terminal and process.exitcode not in (0, None) and not self._cancel.is_set():
                self._fail("The live transcription worker exited unexpectedly.")
        finally:
            try:
                self._events.close()
                self._events.join_thread()
            except (AttributeError, OSError):
                pass

__all__ = [
    "CaptureSource",
    "LiveSegment",
    "LiveTranscriptionConfig",
    "LiveTranscriber",
    "list_application_sources",
    "list_input_devices",
    "list_microphone_sources",
    "list_system_output_sources",
]
