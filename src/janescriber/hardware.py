"""Best-effort hardware detection shared by the CLI and GUI."""

from __future__ import annotations

import os
import platform


def _friendly_cpu_name() -> str:
    """Return the human-readable CPU name where the OS exposes it."""
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                name = " ".join(str(value).split())
                if name:
                    return name
        except (ImportError, OSError, AttributeError):
            pass

    name = " ".join((platform.processor() or platform.machine() or "Host Processor").split())
    return name or "Host Processor"


def detect_hardware() -> dict[str, str | bool]:
    cpu = _friendly_cpu_name()
    cores = os.cpu_count() or 1
    device = "cpu"
    accelerator = "CPU fallback"
    gpu_name = "Not detected"
    torch_version = "Unavailable"
    cuda_runtime = "Unavailable"
    reason = "No supported accelerator detected; using CPU."
    try:
        import torch

        torch_version = str(getattr(torch, "__version__", "Unknown"))
        cuda_runtime = str(getattr(getattr(torch, "version", None), "cuda", None) or "Unavailable")
        if torch.cuda.is_available():
            device = "cuda"
            accelerator = "NVIDIA CUDA / FP16"
            gpu_name = torch.cuda.get_device_name(0)
            reason = "NVIDIA CUDA is available."
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            accelerator = "Apple Metal (MPS)"
            gpu_name = "Apple Silicon GPU"
            reason = "Apple Metal acceleration is available."
        else:
            torch.set_num_threads(cores)
    except Exception:
        reason = "The accelerator runtime was unavailable; using CPU."
    return {
        "cpu": cpu,
        "cores": str(cores),
        "device": device,
        "accelerator": accelerator,
        "gpu": gpu_name,
        "torch_version": torch_version,
        "cuda_runtime": cuda_runtime,
        "reason": reason,
    }
