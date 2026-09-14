# JanesCriber consumer release plan

This is the deferred hardening plan for taking JanesCriber from an internal
beta to a dependable general-purpose Windows application.

## Distribution and installation

- Bundle the runtime or create a real Windows installer instead of relying on
  a thin launcher plus a developer environment.
- Support Python 3.10-3.12 cleanly, with a repair path and clear diagnostics.
- Select CPU Torch on CPU-only systems and CUDA Torch only when NVIDIA is
  available; keep AMD and Intel systems functional through CPU fallback.
- Keep model, scratch, transcript, and package caches on the selected project
  drive, with disk-space checks before large downloads.
- Add install, upgrade, uninstall, and runtime-repair flows.

## Reliability and privacy

- Keep one validated pipeline shared by GUI and CLI.
- Keep media validation, FFmpeg execution, model loading, caching, output
  publication, and cleanup in separate backend modules.
- Add robust model download retry/resume behavior and corrupt-cache recovery.
- Make cancellation and application close terminate active work safely.
- Add single-instance protection and persistent diagnostic logs.
- Keep media local by default and clearly identify any optional network use.

## Quality gates

- Test CPU-only, NVIDIA CUDA, AMD/Intel fallback, missing FFmpeg, invalid media,
  low disk space, corrupt downloads, long media, non-ASCII paths, and no speech.
- Test drag-and-drop, language multi-select, library actions, live monitoring,
  cancellation, closing during work, DPI scaling, and small screens.
- Run clean-machine install, upgrade, uninstall, and antivirus/SmartScreen
  checks.
- Add application licensing and third-party notices.
- Sign the executable and installer, then publish a verified checksum.

## Release gate

Do not label the product consumer-release ready until the clean-machine
installation, runtime selection, lifecycle, signing, and legal gates above have
passed on supported Windows hardware.
