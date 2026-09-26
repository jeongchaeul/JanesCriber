"""Background CPU, RAM, GPU, VRAM, and temperature telemetry for the GUI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .hardware import detect_hardware

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is part of the app runtime
    psutil = None


@dataclass
class HardwareTelemetrySnapshot:
    cpu_system_pct: float = 0.0
    cpu_app_pct: float = 0.0
    ram_system_pct: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_app_mb: float = 0.0
    gpu_system_pct: float = 0.0
    gpu_app_pct: float = 0.0
    gpu_vram_used_mb: int = 0
    gpu_vram_total_mb: int = 0
    gpu_app_vram_mb: int = 0
    gpu_temp_c: int = 0
    gpu_engine_name: str = "3D"
    gpu_name: str = "Not detected"
    gpu_backend: str = "CPU fallback"
    telemetry_source: str = "Unavailable"


class NvidiaSmiProbe:
    """Use the installed NVIDIA driver utility without adding a GPU package."""

    def __init__(self) -> None:
        self.executable = shutil.which("nvidia-smi")
        self.available = bool(self.executable)
        self._creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def sample(self, target_pid: int, active: bool) -> dict[str, int | float | str]:
        if not self.available:
            return {}
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2.0,
                creationflags=self._creationflags,
                check=False,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            fields = [item.strip() for item in result.stdout.splitlines()[0].split(",")]
            if len(fields) < 5:
                return {}
            app_vram = self._process_memory(target_pid) if active else 0
            return {
                "name": fields[0],
                "utilization": float(fields[1]),
                "vram_used": int(float(fields[2])),
                "vram_total": int(float(fields[3])),
                "temperature": int(float(fields[4])),
                "app_vram": app_vram,
            }
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}

    def _process_memory(self, target_pid: int) -> int:
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2.0,
                creationflags=self._creationflags,
                check=False,
            )
            for line in result.stdout.splitlines():
                fields = [item.strip() for item in line.split(",")]
                if len(fields) >= 2 and fields[0].isdigit() and int(fields[0]) == target_pid:
                    return int(float(fields[1]))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return 0


class SystemHardwareMonitor:
    """Continuously sample host and JanesCriber resource usage."""

    def __init__(self, target_pid: int | None = None) -> None:
        self.target_pid = target_pid or os.getpid()
        self.latest_snapshot = HardwareTelemetrySnapshot()
        self.is_processing = False
        self._stop_event = threading.Event()
        self._callback: Callable[[HardwareTelemetrySnapshot], None] | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.gpu_probe = NvidiaSmiProbe()
        self.detected_hardware = detect_hardware()

        if psutil:
            try:
                psutil.cpu_percent(interval=None)
                psutil.Process(self.target_pid).cpu_percent(interval=None)
            except (OSError, psutil.Error):
                pass

    def set_processing(self, active: bool) -> None:
        self.is_processing = active

    def start(self, callback: Callable[[HardwareTelemetrySnapshot], None] | None = None, interval: float = 1.5) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._callback = callback
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True, name="JanesCriberHardwareMonitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def sample_now(self, is_processing: bool | None = None) -> HardwareTelemetrySnapshot:
        active = self.is_processing if is_processing is None else is_processing
        snapshot = HardwareTelemetrySnapshot()
        if psutil:
            try:
                snapshot.cpu_system_pct = round(psutil.cpu_percent(interval=None), 1)
                memory = psutil.virtual_memory()
                snapshot.ram_system_pct = round(memory.percent, 1)
                snapshot.ram_used_gb = round(memory.used / (1024 ** 3), 1)
                snapshot.ram_total_gb = round(memory.total / (1024 ** 3), 1)

                process = psutil.Process(self.target_pid)
                app_cpu = process.cpu_percent(interval=None)
                app_memory = process.memory_info().rss
                if active:
                    for child in process.children(recursive=True):
                        try:
                            app_cpu += child.cpu_percent(interval=None)
                            app_memory += child.memory_info().rss
                        except (OSError, psutil.Error):
                            pass
                snapshot.cpu_app_pct = round(min(100.0, app_cpu / (psutil.cpu_count(logical=True) or 1)), 1)
                snapshot.ram_app_mb = round(app_memory / (1024 * 1024), 1)
            except (OSError, psutil.Error):
                pass

        gpu = self.gpu_probe.sample(self.target_pid, active)
        if gpu:
            snapshot.gpu_system_pct = float(gpu["utilization"])
            snapshot.gpu_app_pct = snapshot.gpu_system_pct if active else 0.0
            snapshot.gpu_vram_used_mb = int(gpu["vram_used"])
            snapshot.gpu_vram_total_mb = int(gpu["vram_total"])
            snapshot.gpu_app_vram_mb = int(gpu["app_vram"])
            snapshot.gpu_temp_c = int(gpu["temperature"])
            snapshot.gpu_engine_name = "CUDA" if active else "3D"
            snapshot.gpu_name = str(gpu["name"])
            snapshot.gpu_backend = "NVIDIA CUDA / FP16"
            snapshot.telemetry_source = "nvidia-smi"
        else:
            snapshot.gpu_backend = str(self.detected_hardware.get("accelerator", "CPU fallback"))
            snapshot.gpu_name = str(self.detected_hardware.get("gpu", "Not detected"))
            if str(self.detected_hardware.get("device", "cpu")) == "cpu":
                snapshot.telemetry_source = "Unavailable"
            else:
                snapshot.telemetry_source = "Torch device detection (utilization unavailable)"

        with self._lock:
            self.latest_snapshot = snapshot
        return snapshot

    def _monitor_loop(self, interval: float) -> None:
        next_sample = time.monotonic()
        while not self._stop_event.wait(timeout=0.25):
            if time.monotonic() < next_sample:
                continue
            next_sample = time.monotonic() + max(0.5, interval)
            snapshot = self.sample_now()
            if self._callback and not self._stop_event.is_set():
                try:
                    self._callback(snapshot)
                except Exception:
                    pass
