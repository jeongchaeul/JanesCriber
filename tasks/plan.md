# JanesCriber Modern Desktop UI Plan

## Approach

Build the Tauri 2 surface in vertical slices while keeping the Python launcher
working. The existing Python pipeline remains authoritative; the UI is a new
client of that pipeline.

## Slices

1. **Contract and scaffold**
   - Record the feature map and design contract.
   - Add a Tauri 2 + React + TypeScript + Tailwind + Motion scaffold.
   - Add restrained family styling, responsive shell, sidebar collapse, and
     native window configuration.
2. **Backend bridge**
   - Add JSON-lines service mode to Python.
   - Add Rust process supervision and event forwarding.
   - Cover status, logs, cancellation, and shutdown behavior.
3. **Core transcription**
   - Implement studio drag/drop, native browse, all engines/models/languages,
     progress stages, console output, cancellation, and output folder actions.
   - Implement Transcript Library and the timestamp-aware reader.
4. **Live and telemetry**
   - Expose microphone/system/application sources, live notes, save/stop,
     hardware telemetry, and pipeline tracker.
5. **Packaging and cleanup**
   - Add portable build integration and feature-parity checks against the
     legacy launcher.
   - Consolidate generated build output under artifacts, prune verified old
     staging, and confirm project-local caches.

## Verification gates

- Python tests remain green after every backend slice.
- npm run build, frontend tests, cargo check, and Tauri smoke startup pass.
- The legacy launcher still starts.
- The new shell can start without a globally installed Python when a bundled
  backend is present.
- No generated artifacts or model weights are committed.

## Post-v1 improvement wave

The next work is focused on making the existing product safer to release and
more dependable for ordinary users before adding additional model families.

### Slice A: Release confidence

- Add CI checks for Python, frontend, and Tauri source health. **Done:**
  `.github/workflows/ci.yml` runs the cross-layer gates.
- Add a release-artifact validator for installer manifests and SHA-256 files.
  **Done:** the validator is also enforced by the consumer build script.
- Document the exact separation between source builds, portable ZIPs, and the
  consumer installer.

### Slice B: Backend reliability

- Add visible live-capture backpressure reporting instead of silently dropping
  audio when the bounded queue is saturated. **Done:** drops are bounded,
  counted, throttled, and surfaced to the live console.
- Add reproducible model metadata and safer external-download diagnostics.
- Add regression coverage for the new diagnostics. **Done:** release, live,
  format, library, and version checks are covered by the Python suite.

### Slice C: Consumer workflow

- Add first-class export formats only where the existing transcript contract can
  support them without breaking the default TXT output. **Done:** TXT, SRT,
  VTT, and JSON are shared by the modern and legacy launchers.
- Keep the default local/private behavior and legacy recovery path unchanged.

### Slice D: Release gate

- Run all local checks and record any unavailable environment checks honestly.
- Rebuild the packaged installer only after the Rust toolchain is available.
- Perform clean-machine install, upgrade, live capture, and uninstall checks.
