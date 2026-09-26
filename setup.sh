#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#             JanesCriber - Unix Automated Setup
#              (Linux and macOS Support)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

WITH_QWEN=0
for arg in "$@"; do
    case "$arg" in
        qwen|--with-qwen|-WithQwen)
            WITH_QWEN=1
            ;;
    esac
done

echo ""
echo "============================================================"
echo "             JanesCriber - Automated Setup"
echo "============================================================"
echo ""

# Check prerequisites
if ! command -v uv &>/dev/null; then
    echo "Error: 'uv' was not found. Install it from https://docs.astral.sh/uv/ and run setup again." >&2
    exit 1
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "Error: 'ffmpeg' was not found. Install ffmpeg via your package manager (brew/apt/pacman/dnf) and run setup again." >&2
    exit 1
fi

if ! command -v ffprobe &>/dev/null; then
    echo "Error: 'ffprobe' was not found. Install the complete ffmpeg package and run setup again." >&2
    exit 1
fi

export UV_CACHE_DIR="$SCRIPT_DIR/.cache/uv-cache"
mkdir -p "$UV_CACHE_DIR"

# Platform and accelerator detection
OS_TYPE="$(uname -s)"
HARDWARE_PROFILE="CPU base runtime"
TORCH_VERSION="2.7.1"
TORCH_EXTRA="cpu"
TORCH_INDEX="https://download.pytorch.org/whl/cpu"

if [[ "$OS_TYPE" == "Darwin" ]]; then
    # macOS - PyTorch includes native Metal (MPS) in default wheels
    HARDWARE_PROFILE="Apple Silicon / Metal (MPS)"
    TORCH_INDEX="https://pypi.org/simple"
elif [[ "$OS_TYPE" == "Linux" ]]; then
    if command -v nvidia-smi &>/dev/null; then
        HARDWARE_PROFILE="NVIDIA CUDA"
        TORCH_EXTRA="cuda"
        TORCH_INDEX="https://download.pytorch.org/whl/cu128"
    elif command -v rocm-smi &>/dev/null || [[ -d "/opt/rocm" ]]; then
        HARDWARE_PROFILE="AMD ROCm / HIP"
        TORCH_EXTRA="rocm"
        TORCH_INDEX="https://download.pytorch.org/whl/rocm6.2"
    fi
fi

echo "Hardware profile: $HARDWARE_PROFILE"

# Python interpreter selection: prefer 3.11 or 3.12
PYTHON_BIN=""
for py_candidate in python3.11 python3.12 python3.10 python3; do
    if command -v "$py_candidate" &>/dev/null; then
        PY_VER="$("$py_candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)"
        if [[ "$PY_VER" =~ ^(3\.10|3\.11|3\.12)$ ]]; then
            PYTHON_BIN="$(command -v "$py_candidate")"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "No supported host Python (3.10-3.12) found. Installing managed Python 3.11 with uv..."
    uv python install 3.11 --install-dir "$SCRIPT_DIR/.cache/python"
    PYTHON_BIN="$(uv python find 3.11)"
fi

echo "Using Python: $PYTHON_BIN"

echo "Synchronizing project virtual environment..."
uv sync --locked --python "$PYTHON_BIN"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [[ "$OS_TYPE" == "Darwin" ]]; then
    echo "Installing PyTorch with Apple Metal (MPS) support..."
    uv pip install --python "$VENV_PYTHON" "torch==$TORCH_VERSION" --index-url "https://pypi.org/simple"
elif [[ "$TORCH_EXTRA" == "cuda" ]]; then
    echo "Installing PyTorch with CUDA support..."
    uv pip install --python "$VENV_PYTHON" "torch==${TORCH_VERSION}+cu128" --index-url "$TORCH_INDEX" --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
elif [[ "$TORCH_EXTRA" == "rocm" ]]; then
    echo "Installing PyTorch with ROCm support..."
    uv pip install --python "$VENV_PYTHON" "torch==${TORCH_VERSION}+rocm6.2" --index-url "$TORCH_INDEX" --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
else
    echo "Installing PyTorch with CPU support..."
    uv pip install --python "$VENV_PYTHON" "torch==${TORCH_VERSION}+cpu" --index-url "$TORCH_INDEX" --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
fi

if [[ "$WITH_QWEN" -eq 1 ]]; then
    echo "Installing optional Qwen3-ASR backend..."
    uv pip install --python "$VENV_PYTHON" "qwen-asr==0.0.6" --index-url "https://pypi.org/simple"
    uv pip install --python "$VENV_PYTHON" "torchvision==0.22.1" --index-url "$TORCH_INDEX" --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
fi

echo ""
echo "Setup complete! To run JanesCriber Studio:"
echo "  $SCRIPT_DIR/JanesCriberStudio  (or ./JanesCriberStudio.exe on Windows)"
echo "or for CLI transcription:"
echo "  $SCRIPT_DIR/.venv/bin/python -m janescriber /path/to/media.mp4"
