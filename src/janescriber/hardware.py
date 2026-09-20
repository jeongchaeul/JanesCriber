"""Best-effort hardware detection shared by the CLI and GUI."""

from __future__ import annotations

import os
import platform
from typing import Any


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


def _safe_device_name(backend: Any, fallback: str) -> str:
    try:
        name = backend.get_device_name(0)
    except Exception:
        return fallback
    return str(name or fallback)


def _select_accelerator(torch_module: Any, *, directml_module: Any | None = None) -> dict[str, str]:
    """Select the fastest usable local Torch device in a stable priority order.

    ROCm intentionally uses Torch's CUDA API and therefore shares the ``cuda``
    device string. DirectML is kept optional because its PyTorch plugin is a
    separate Windows package and has a narrower operator/runtime matrix.
    """
    cuda = getattr(torch_module, "cuda", None)
    try:
        cuda_available = bool(cuda and cuda.is_available())
    except Exception:
        cuda_available = False
    if cuda_available:
        version = getattr(torch_module, "version", None)
        hip_runtime = str(getattr(version, "hip", None) or "")
        if hip_runtime:
            return {
                "device": "cuda",
                "accelerator": "AMD ROCm / HIP",
                "gpu": _safe_device_name(cuda, "AMD GPU"),
                "runtime": hip_runtime,
                "reason": "AMD ROCm/HIP is available through Torch's CUDA-compatible API.",
            }
        return {
            "device": "cuda",
            "accelerator": "NVIDIA CUDA / FP16",
            "gpu": _safe_device_name(cuda, "NVIDIA GPU"),
            "runtime": str(getattr(version, "cuda", None) or "Unavailable"),
            "reason": "NVIDIA CUDA is available.",
        }

    xpu = getattr(torch_module, "xpu", None)
    try:
        xpu_available = bool(xpu and xpu.is_available())
    except Exception:
        xpu_available = False
    if xpu_available:
        return {
            "device": "xpu",
            "accelerator": "Intel XPU",
            "gpu": _safe_device_name(xpu, "Intel GPU"),
            "runtime": "XPU",
            "reason": "Intel XPU acceleration is available.",
        }

    backends = getattr(torch_module, "backends", None)
    mps = getattr(backends, "mps", None)
    try:
        mps_available = bool(mps and mps.is_available())
    except Exception:
        mps_available = False
    if mps_available:
        return {
            "device": "mps",
            "accelerator": "Apple Metal (MPS)",
            "gpu": "Apple GPU",
            "runtime": "MPS",
            "reason": "Apple Metal acceleration is available.",
        }

    if directml_module is None:
        try:
            import torch_directml as directml_module
        except (ImportError, OSError, RuntimeError):
            directml_module = None
    if directml_module is not None:
        try:
            directml_module.device()
        except (AttributeError, OSError, RuntimeError):
            pass
        else:
            return {
                "device": "dml",
                "accelerator": "Windows DirectML",
                "gpu": "DirectX 12 GPU",
                "runtime": "DirectML",
                "reason": "Windows DirectML acceleration is available.",
            }

    return {
        "device": "cpu",
        "accelerator": "CPU fallback",
        "gpu": "Not detected",
        "runtime": "CPU",
        "reason": "No supported accelerator detected; using CPU.",
    }


def resolve_accelerator_device(device: str, torch_module: Any) -> Any:
    """Resolve the application device label into a Torch-compatible device."""
    if device != "dml":
        return device
    try:
        import torch_directml
    except (ImportError, OSError, RuntimeError) as exc:
        raise RuntimeError("Windows DirectML is selected but torch-directml is unavailable.") from exc
    try:
        return torch_directml.device()
    except Exception as exc:
        raise RuntimeError(f"Windows DirectML could not create a device: {exc}") from exc


def clear_accelerator_cache(torch_module: Any, device: str) -> None:
    """Release cached allocations when a GPU load fails or a job ends."""
    backend = getattr(torch_module, device, None)
    direct_empty_cache = getattr(backend, "empty_cache", None)
    if callable(direct_empty_cache):
        try:
            direct_empty_cache()
        except Exception:
            pass
        return
    memory = getattr(backend, "memory", None)
    empty_cache = getattr(memory, "empty_cache", None)
    if callable(empty_cache):
        try:
            empty_cache()
        except Exception:
            pass


def detect_hardware() -> dict[str, str | bool]:
    cpu = _friendly_cpu_name()
    cores = os.cpu_count() or 1
    torch_version = "Unavailable"
    cuda_runtime = "Unavailable"
    selection = {
        "device": "cpu",
        "accelerator": "CPU fallback",
        "gpu": "Not detected",
        "runtime": "CPU",
        "reason": "No supported accelerator detected; using CPU.",
    }
    try:
        import torch

        torch_version = str(getattr(torch, "__version__", "Unknown"))
        selection = _select_accelerator(torch)
        cuda_runtime = str(selection["runtime"])
        if selection["device"] == "cpu":
            torch.set_num_threads(cores)
    except Exception:
        selection["reason"] = "The accelerator runtime was unavailable; using CPU."
    return {
        "cpu": cpu,
        "cores": str(cores),
        **selection,
        "torch_version": torch_version,
        "cuda_runtime": cuda_runtime,
    }
