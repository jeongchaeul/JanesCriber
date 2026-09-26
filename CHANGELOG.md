# Changelog

All notable JanesCriber changes are documented here.

## [2.0.0] - 2026-09-27

### Added

- Native Tauri Studio interface promoted to primary, exclusive desktop interface.
- Zero-terminal, zero-prerequisite standalone consumer installer and portable package matching JaneConverter standards.
- Bundled internal Python engine runtime (`JanesCriberEngine`) with PyTorch, Whisper, and Vosk pre-packaged.
- Bundled static FFmpeg and ffprobe binaries.
- Multi-OS packaging support: native Linux tarball pipeline and macOS arm64/x86_64 DMG pipelines.
- Live hardware telemetry panel with dynamic CPU, memory, and engine health monitoring.
- Studio release checking against the official GitHub Releases page with manual update action.

### Removed

- Deprecated legacy CustomTkinter Python GUI (`gui.py`, `file_drop.py`, `gui_common.py`) and transitional headers.

## [1.0.0] - 2026-09-20

### Added

- First public release of the local-first audio and video transcription
  workflow.
- Whisper, Vosk/Kaldi, Wav2Vec2, and optional Qwen3-ASR backends.
- Timestamped UTF-8 transcript output in the project-local `Transcripts`
  folder.
- Live microphone, system-output, and visible application-output capture.
- Searchable multilingual selection, including Tagalog/Filipino.
- Transcript Library with in-app reading, folder access, refresh, and safe
  deletion actions.
- JanesCriber Studio native desktop interface alongside the legacy Python UI.
- Hardware and pipeline views with live resource telemetry and progress logs.
- GPU-aware runtime selection for CUDA/ROCm, Intel XPU, Apple MPS, Windows
  DirectML, and CPU fallback.
- Project-local model, Python, uv, temporary, Torch, and Hugging Face cache
  paths to reduce unnecessary system-drive usage.

### Changed

- Setup now detects a usable hardware profile and installs the matching Torch
  runtime instead of assuming NVIDIA CUDA.
- Accelerator model loading retries on CPU when the selected device cannot
  initialize the requested model.
- Windows setup prefers supported Python versions and can install a managed
  project-local interpreter when needed.
- Release metadata is aligned to version `1.0.0`.

### Notes

- Qwen3-ASR is optional and file-only in this release.
- Windows DirectML is a compatibility path; native CUDA, ROCm, XPU, or MPS
  remains preferable when a stable compatible runtime is available.
- Portable release executables are unsigned unless a maintainer supplies a
  signing certificate during the build.
