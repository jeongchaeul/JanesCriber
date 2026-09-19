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

