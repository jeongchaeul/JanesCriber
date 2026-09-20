# JanesCriber unified installer plan

## Overview

Add a consumer-facing Windows installer without removing the existing source,
CLI, or legacy Python recovery path. The consumer flow should present one
`JanesCriber-Setup.exe`, keep the native Studio surface and packaged Python
backend together, select a compatible runtime on first launch, and place large
mutable data on a user-selected drive.

## Safety-net contract

- `setup.bat` and `install.ps1` remain the developer/nerdy installation path.
- The CLI and legacy Python UI remain available for diagnosis and recovery.
- The unified installer is additive; it does not replace the backend pipeline.
- Model weights and accelerator-specific packages are not silently duplicated
  for every vendor inside the installer.
- Uninstall must not delete `Transcripts` or downloaded models without an
  explicit user choice.

## Architecture decisions

- Use the existing Tauri 2 Studio bundle as the consumer shell and NSIS as the
  single Windows setup executable.
- Keep the Python ASR runtime packaged as an internal backend resource rather
  than rewriting Whisper, Qwen, Vosk, or Torch in Rust.
- Separate immutable application files from mutable data. The installer may
  choose the application directory and a data directory independently.
- Perform first-run environment checks and accelerator selection through the
  existing project-local setup logic, with clear progress and a repair path.
- Build an online universal installer first; provide a larger offline bundle as
  a later release artifact rather than forcing every model and GPU runtime into
  the default download. The consumer NSIS package uses a CPU-safe Torch
  runtime so it remains below NSIS' practical single-file size limit; the
  developer path remains available for hardware-specific accelerator runtimes.

## Task list

### Phase 1: Packaging foundation

- [ ] Define a stable portable bundle contract for Studio, the packaged Python
      backend, FFmpeg, assets, licenses, and runtime metadata.
- [ ] Add a consumer build script that stages one complete application tree and
      invokes the Tauri NSIS target.
- [ ] Add a preflight manifest and validation command that fails before
      packaging when the backend, Studio executable, or FFmpeg is missing.

### Checkpoint: Packaging foundation

- [ ] Existing `setup.bat` and CLI still work.
- [ ] Portable staging contains no source checkout paths or developer-only
      virtual-environment assumptions.
- [ ] Tauri production build succeeds with the staged backend resource.

### Phase 2: Consumer first-run bootstrap

- [ ] Add a first-run data-directory chooser with a project-local fallback.
- [ ] Detect the hardware profile and select CUDA, DirectML, another supported
      accelerator, or CPU without requiring the user to understand Torch.
- [ ] Add a repair path that re-runs runtime preparation without deleting
      transcripts or models.
- [ ] Keep model downloads lazy and show their destination before downloading.

### Checkpoint: Consumer install

- [ ] Clean-machine install starts Studio without a developer Python install.
- [ ] First-run setup can complete on NVIDIA, non-NVIDIA Windows, and CPU-only
      machines.
- [ ] A failed optional accelerator setup leaves a working CPU fallback.

### Phase 3: Recovery and release hardening

- [ ] Preserve an explicit “Open legacy/recovery UI” action.
- [ ] Add uninstall/repair behavior that preserves user data by default.
- [ ] Sign the installer and binaries when a maintainer certificate is
      available.
- [ ] Test install, upgrade, repair, uninstall, and rollback on clean Windows
      machines.
- [ ] Publish checksums and a consumer release guide.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Torch/GPU wheels are large and vendor-specific | High | Keep the consumer installer CPU-safe and use the developer path for hardware-specific runtimes; keep CPU fallback. |
| One-file Python packaging extracts to temp | High | Use a packaged one-directory backend inside the installer resources. |
| Program Files is not writable | High | Store transcripts, models, cache, logs, and temp in a separate data directory. |
| WebView2 is missing | Medium | Use the Tauri installer bootstrapper and document offline installer behavior. |
| Optional Qwen and DirectML packages conflict | Medium | Keep the current explicit incompatibility guard and expose repair guidance. |
| Uninstall removes valuable transcripts | High | Preserve the data directory unless the user explicitly opts in to deletion. |

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix desktop-ui test
npm --prefix desktop-ui run build
.\build_consumer_installer.ps1
```
