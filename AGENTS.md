# AGENTS.md

Guidance for agents and contributors working in this repository.

## Project

JanesCriber is a fast, 100% offline audio and video transcription studio with a Tauri desktop app, a Python CLI, and multi-backend speech recognition (Whisper, Vosk, Qwen3-ASR, Wav2Vec2). Everything runs locally with hardware acceleration (CUDA, ROCm, DirectML, Apple MPS, Intel XPU, and CPU fallback).

## Repository layout

- `src/janescriber/` - Python transcription engine and worker bridge service
- `tests/` - Python test suite
- `desktop-ui/` - Tauri 2 + React + TypeScript desktop app (`src-tauri/` holds the Rust bridge)
- `packaging/` - release build scripts, engine smoke test, and packaging contracts
- `.github/workflows/` - CI and quality gates

## Toolchains and runtimes

- Python backend uses `uv`. The pinned interpreter is Python 3.11 (`.python-version`). Declared constraint is `requires-python = ">=3.10,<3.13"`.
- Rust uses the latest stable toolchain with Cargo.
- Node.js 22 and npm for the frontend.
- Run Python through `uv` only (`uv run`, `uv sync`). Do not invoke bare `python`, `python3`, or `pip` without project context.

## Commands

Setup:

```bash
uv sync --locked
cd desktop-ui && npm ci
```

Python tests:

```bash
uv run --locked pytest tests/ -v
```

Engine smoke test:

```powershell
uv run --locked python packaging/smoke_test_engine.py --runtime-bin "D:\Programs\JanesCriber\runtime\bin" --work-directory "temp/smoke"
```

Desktop UI:

```bash
cd desktop-ui
npm test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
```

Rebuilding Executables:

See `packaging/REBUILD.md` for complete build and local deployment steps.
- **Desktop UI (`janescriber-studio.exe`):** NEVER run bare `cargo build` in development mode. Always run `npm run tauri:build -- --no-bundle` inside `desktop-ui/` so production web assets are compiled and embedded directly into the standalone binary.
- **Engine (`JanesCriberEngine.exe`):** Run PyInstaller via `uv run` collecting `whisper`, `vosk`, and submodules `transformers.models.wav2vec2`.

## Conventions

- Keep build and packaging scripts under `packaging/`. Do not add build scripts to the repository root.
- The version is a single source in `src/janescriber/__init__.py`. Bump it there; release tags must match `v<version>`.
- Privacy and offline execution are paramount: zero cloud telemetry, zero remote network calls during transcription. All models stay inside the configured data directory cache (`.cache/`).
- Sanitize Windows paths when interacting with the native bridge: strip `\\?\` and `\\?\UNC\` before saving or passing paths to Python.
