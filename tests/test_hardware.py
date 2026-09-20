from types import SimpleNamespace

from janescriber.hardware import _select_accelerator, resolve_accelerator_device


class _Unavailable:
    def is_available(self):
        return False


class _Cuda:
    def __init__(self, available=True, name="GPU"):
        self.available = available
        self.name = name

    def is_available(self):
        return self.available

    def get_device_name(self, _index):
        return self.name


def _torch(*, cuda=None, hip=None, xpu=None, mps=None):
    return SimpleNamespace(
        cuda=cuda or _Unavailable(),
        xpu=xpu,
        version=SimpleNamespace(cuda="12.8" if hip is None else None, hip=hip),
        backends=SimpleNamespace(mps=mps or _Unavailable()),
    )


def test_prefers_nvidia_cuda_over_other_accelerators():
    selection = _select_accelerator(_torch(cuda=_Cuda(name="NVIDIA RTX"), xpu=_Cuda(name="Intel Arc")))

    assert selection["device"] == "cuda"
    assert selection["accelerator"] == "NVIDIA CUDA / FP16"


def test_identifies_amd_rocm_through_torch_cuda_api():
    selection = _select_accelerator(_torch(cuda=_Cuda(name="AMD Radeon"), hip="6.4"))

    assert selection["device"] == "cuda"
    assert selection["accelerator"] == "AMD ROCm / HIP"
    assert selection["runtime"] == "6.4"


def test_uses_intel_xpu_when_cuda_is_unavailable():
    selection = _select_accelerator(_torch(xpu=_Cuda(name="Intel Arc")))

    assert selection["device"] == "xpu"
    assert selection["accelerator"] == "Intel XPU"


def test_uses_apple_mps_when_cuda_and_xpu_are_unavailable():
    selection = _select_accelerator(_torch(mps=_Cuda(name="Apple GPU")))

    assert selection["device"] == "mps"
    assert selection["accelerator"] == "Apple Metal (MPS)"


def test_uses_optional_directml_backend_when_available():
    directml = SimpleNamespace(device=lambda: object())
    selection = _select_accelerator(_torch(), directml_module=directml)

    assert selection["device"] == "dml"
    assert selection["accelerator"] == "Windows DirectML"


def test_falls_back_to_cpu_without_a_supported_accelerator():
    selection = _select_accelerator(_torch())

    assert selection["device"] == "cpu"
    assert selection["accelerator"] == "CPU fallback"


def test_directml_device_is_resolved_only_when_selected(monkeypatch):
    class DirectML:
        @staticmethod
        def device():
            return "directml-device"

    monkeypatch.setitem(__import__("sys").modules, "torch_directml", DirectML)

    assert resolve_accelerator_device("dml", object()) == "directml-device"
    assert resolve_accelerator_device("cpu", object()) == "cpu"
