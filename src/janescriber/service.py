"""JSON-lines bridge used by the modern Tauri desktop surface.

The service is deliberately a thin adapter around the existing Python
contracts. Long-running ASR and live-capture work stays in child processes so
closing or cancelling a job releases native model memory instead of keeping it
inside the UI process.
"""

from __future__ import annotations

import json
import multiprocessing
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hardware import detect_hardware
from .hardware_monitor import SystemHardwareMonitor
from .languages import ALL_AVAILABLE_LANGUAGES
from .library import discover_transcripts, is_managed_transcript, read_transcript
from .live import (
    CaptureSource,
    LiveProcessController,
    LiveTranscriptionConfig,
    list_application_sources,
    list_microphone_sources,
    list_system_output_sources,
)
from .paths import project_dir, runtime_paths
from .pipeline import run_transcription_job
from .pipeline_config import SUPPORTED_ENGINES, SUPPORTED_MODELS
from .qwen_backend import QWEN_MODEL_LABELS
from .runtime import configure_runtime
from .vosk_backend import VOSK_MODEL_LABELS
from .wav2vec_backend import WAV2VEC2_MODEL_LABELS


@dataclass
class _Job:
    request_id: str
    process: multiprocessing.Process
    events: Any
    cancel: Any
    cancel_requested: bool = False
    terminal: bool = False


class JsonLinesService:
    def __init__(self) -> None:
        self.base = project_dir()
        self.paths = configure_runtime(self.base)
        self.context = multiprocessing.get_context("spawn")
        self.monitor = SystemHardwareMonitor(target_pid=None)
        self.jobs: dict[str, _Job] = {}
        self.live_sessions: dict[str, LiveProcessController] = {}
        self.lock = threading.RLock()
        self.output_lock = threading.Lock()

    def send(self, payload: dict[str, Any]) -> None:
        # Keep the protocol ASCII-safe on stock Windows console code pages.
        # The frontend still receives Unicode after JSON decoding.
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with self.output_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def response(self, request_id: str, data: Any = None, error: str | None = None) -> None:
        body: dict[str, Any] = {"type": "response", "id": request_id, "ok": error is None}
        if error is None:
            body["data"] = data
        else:
            body["error"] = error
        self.send(body)

    def event(self, request_id: str, name: str, **values: Any) -> None:
        body: dict[str, Any] = {"type": "event", "id": request_id, "event": name}
        body.update(values)
        self.send(body)

    def handle(self, request_id: str, operation: str, payload: dict[str, Any]) -> None:
        try:
            handler = getattr(self, f"_op_{operation.replace('.', '_')}", None)
            if handler is None:
                raise ValueError(f"Unknown bridge operation: {operation}")
            data = handler(request_id, payload)
            if data is not _ASYNC:
                self.response(request_id, data)
        except Exception as exc:
            self.response(request_id, error=f"{type(exc).__name__}: {exc}")

    def _op_bootstrap(self, _request_id: str, _payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "projectRoot": str(self.base),
            "transcriptRoot": str(self.paths["transcripts"]),
            "cacheRoot": str(self.paths["cache"]),
            "tempRoot": str(self.paths["temp"]),
            "hardware": detect_hardware(),
            "engines": list(SUPPORTED_ENGINES),
            "models": {
                "whisper": [{"id": value, "label": value.title()} for value in SUPPORTED_MODELS],
                "qwen3-asr": [{"id": key, "label": label} for key, label in QWEN_MODEL_LABELS.items()],
                "vosk": [{"id": key, "label": label} for key, label in VOSK_MODEL_LABELS.items()],
                "wav2vec2": [{"id": key, "label": label} for key, label in WAV2VEC2_MODEL_LABELS.items()],
            },
            "languages": [{"code": code, "name": name} for code, name in ALL_AVAILABLE_LANGUAGES.items()],
        }

    def _op_hardware_snapshot(self, _request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        active = bool(payload.get("active", False)) or bool(self.jobs)
        snapshot = self.monitor.sample_now(is_processing=active)
        return {
            "cpuSystemPct": snapshot.cpu_system_pct,
            "cpuAppPct": snapshot.cpu_app_pct,
            "ramSystemPct": snapshot.ram_system_pct,
            "ramUsedGb": snapshot.ram_used_gb,
            "ramTotalGb": snapshot.ram_total_gb,
            "ramAppMb": snapshot.ram_app_mb,
            "gpuSystemPct": snapshot.gpu_system_pct,
            "gpuAppPct": snapshot.gpu_app_pct,
            "gpuVramUsedMb": snapshot.gpu_vram_used_mb,
            "gpuVramTotalMb": snapshot.gpu_vram_total_mb,
            "gpuAppVramMb": snapshot.gpu_app_vram_mb,
            "gpuTempC": snapshot.gpu_temp_c,
            "gpuEngineName": snapshot.gpu_engine_name,
            "gpuName": snapshot.gpu_name,
            "gpuBackend": snapshot.gpu_backend,
            "telemetrySource": snapshot.telemetry_source,
            "active": active,
        }

    def _op_library_list(self, _request_id: str, _payload: dict[str, Any]) -> list[dict[str, Any]]:
        entries = discover_transcripts(self.paths["transcripts"])
        return [
            {
                "name": entry.path.name,
                "path": str(entry.path),
                "size": entry.size,
                "modified": entry.modified,
            }
            for entry in entries
        ]

    def _managed_path(self, raw_path: Any) -> Path:
        candidate = Path(str(raw_path or "")).resolve()
        if not is_managed_transcript(candidate, self.paths["transcripts"]):
            raise ValueError("That file is not a managed JanesCriber transcript.")
        return candidate

    def _op_library_read(self, _request_id: str, payload: dict[str, Any]) -> dict[str, str]:
        path = self._managed_path(payload.get("path"))
        return {"path": str(path), "name": path.name, "content": read_transcript(path, self.paths["transcripts"])}

    def _op_library_delete(self, _request_id: str, payload: dict[str, Any]) -> dict[str, bool]:
        path = self._managed_path(payload.get("path"))
        path.unlink()
        return {"deleted": True}

    def _op_open_folder(self, _request_id: str, _payload: dict[str, Any]) -> dict[str, str]:
        return {"path": str(self.paths["transcripts"])}

    def _op_transcribe_start(self, request_id: str, payload: dict[str, Any]) -> object:
        source = str(payload.get("source") or "").strip()
        if not source:
            raise ValueError("Choose an audio or video file first.")
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        events = self.context.Queue(maxsize=512)
        cancel = self.context.Event()
        process = self.context.Process(
            target=run_transcription_job,
            kwargs={
                "source": source,
                "engine": str(payload.get("engine") or "whisper"),
                "model_name": str(payload.get("model") or "turbo"),
                "language": ",".join(str(value) for value in (payload.get("languages") or [])) or None,
                "paths": self.paths,
                "overwrite": bool(payload.get("overwrite", False)),
                "use_cache": bool(payload.get("useCache", True)),
                "event_queue": events,
                "cancel": cancel,
            },
            name="JanesCriberTranscriptionWorker",
        )
        job = _Job(request_id, process, events, cancel)
        with self.lock:
            self.jobs[job_id] = job
        process.start()
        threading.Thread(target=self._watch_job, args=(job_id, job), daemon=True, name="JanesCriberJobBridge").start()
        self.event(request_id, "job-accepted", jobId=job_id)
        return {"jobId": job_id}

    def _watch_job(self, job_id: str, job: _Job) -> None:
        terminal = False

        def forward(item: Any) -> None:
            nonlocal terminal
            if not item:
                return
            kind = item[0]
            if kind == "log":
                self.event(job.request_id, "log", jobId=job_id, message=str(item[1]))
            elif kind == "progress":
                self.event(job.request_id, "progress", jobId=job_id, progress=float(item[1]), message=str(item[2]))
            elif kind == "completed":
                terminal = True
                self.event(job.request_id, "completed", jobId=job_id, output=str(item[1]))
            elif kind == "cancelled":
                terminal = True
                self.event(job.request_id, "cancelled", jobId=job_id, message="Transcription cancelled.")
            elif kind == "error":
                terminal = True
                self.event(job.request_id, "error", jobId=job_id, message=str(item[1]))

        try:
            while job.process.is_alive():
                try:
                    forward(job.events.get(timeout=0.2))
                except queue.Empty:
                    pass
            job.process.join(timeout=1)
            while True:
                try:
                    forward(job.events.get_nowait())
                except queue.Empty:
                    break
            if not terminal:
                if job.cancel_requested:
                    self.event(job.request_id, "cancelled", jobId=job_id, message="Transcription cancelled.")
                elif job.process.exitcode not in (0, None):
                    self.event(job.request_id, "error", jobId=job_id, message="The transcription worker exited unexpectedly.")
                else:
                    self.event(job.request_id, "error", jobId=job_id, message="The transcription worker ended without a result.")
        finally:
            with self.lock:
                self.jobs.pop(job_id, None)
            try:
                job.events.close()
                job.events.join_thread()
            except (AttributeError, OSError):
                pass

    def _op_transcribe_cancel(self, _request_id: str, payload: dict[str, Any]) -> dict[str, bool]:
        job_id = str(payload.get("jobId") or "")
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return {"cancelled": False}
            job.cancel_requested = True
            job.cancel.set()
        threading.Thread(target=self._finish_cancel, args=(job,), daemon=True).start()
        return {"cancelled": True}

    @staticmethod
    def _finish_cancel(job: _Job) -> None:
        job.process.join(timeout=2.0)
        if job.process.is_alive():
            job.process.terminate()
            job.process.join(timeout=1.0)

    def _op_live_sources(self, _request_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        mode = str(payload.get("mode") or "microphone")
        if mode == "system":
            sources = list_system_output_sources()
        elif mode == "application":
            sources = list_application_sources()
        else:
            sources = list_microphone_sources()
        return [
            {"kind": source.kind, "label": source.label, "identifier": source.identifier, "pid": source.pid}
            for source in sources
        ]

    def _op_live_start(self, request_id: str, payload: dict[str, Any]) -> dict[str, str]:
        mode = str(payload.get("mode") or "microphone")
        sources = self._op_live_sources(request_id, {"mode": mode})
        requested = payload.get("source") or {}
        selected = next(
            (item for item in sources if item.get("identifier") == requested.get("identifier")),
            sources[0] if sources else None,
        )
        if not selected:
            raise RuntimeError("No live audio source is available for this capture mode.")
        source = CaptureSource(
            kind=selected["kind"],
            label=selected["label"],
            identifier=selected.get("identifier"),
            pid=selected.get("pid"),
        )
        config = LiveTranscriptionConfig(
            engine=str(payload.get("engine") or "whisper"),
            model_name=str(payload.get("model") or "tiny"),
            language=tuple(str(value) for value in (payload.get("languages") or [])),
        )
        session_id = f"live-{uuid.uuid4().hex[:12]}"

        def status(message: str) -> None:
            self.event(request_id, "live-status", sessionId=session_id, message=message)

        def text(value: str, _segments: list[Any]) -> None:
            self.event(request_id, "live-text", sessionId=session_id, text=value)

        def finished(path: Path | None) -> None:
            self.event(request_id, "live-finished", sessionId=session_id, output=str(path) if path else "")
            with self.lock:
                self.live_sessions.pop(session_id, None)

        def failed(error: BaseException) -> None:
            self.event(request_id, "live-error", sessionId=session_id, message=str(error))
            with self.lock:
                self.live_sessions.pop(session_id, None)

        controller = LiveProcessController(
            self.paths,
            config,
            capture_source=source,
            on_status=status,
            on_text=text,
            on_finished=finished,
            on_error=failed,
        )
        with self.lock:
            self.live_sessions[session_id] = controller
        controller.start()
        return {"sessionId": session_id, "source": selected["label"]}

    def _op_live_stop(self, _request_id: str, payload: dict[str, Any]) -> dict[str, bool]:
        session_id = str(payload.get("sessionId") or "")
        with self.lock:
            controller = self.live_sessions.get(session_id)
        if controller:
            controller.stop()
            with self.lock:
                self.live_sessions.pop(session_id, None)
        return {"stopped": True}

    def shutdown(self) -> None:
        with self.lock:
            jobs = list(self.jobs.values())
            live = list(self.live_sessions.values())
        for job in jobs:
            job.cancel_requested = True
            job.cancel.set()
            if job.process.is_alive():
                job.process.terminate()
        for controller in live:
            controller.stop(timeout=1)


_ASYNC = object()


def run_service() -> int:
    multiprocessing.freeze_support()
    service = JsonLinesService()
    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                request_id = str(request.get("id") or uuid.uuid4().hex)
                operation = str(request.get("operation") or "")
                payload = request.get("payload") or {}
                if not isinstance(payload, dict):
                    raise ValueError("Bridge payload must be an object.")
                service.handle(request_id, operation, payload)
            except Exception as exc:
                service.response(str(uuid.uuid4().hex), error=f"{type(exc).__name__}: {exc}")
    finally:
        service.shutdown()
    return 0


__all__ = ["run_service"]
