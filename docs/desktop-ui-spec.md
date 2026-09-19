# JanesCriber Desktop UI Specification

## Objective

Add a modern native desktop surface beside the existing Python launcher. The
new surface must feel like the Janes family portfolio and JaneClipper desktop
programs while keeping the current local-first transcription engine as the
single source of truth.

## Product contract

- The Python launcher remains available as a fallback and compatibility path.
- The Tauri app is a separate executable named **JanesCriber Studio**.
- Rust owns window lifecycle, native file/folder dialogs, child-process
  control, and the bridge to the Python engine.
- React and TypeScript own the UI state and accessible presentation.
- Tailwind owns layout and design tokens; Motion owns restrained transitions.
- Runtime data stays beside the application whenever possible: Transcripts,
  .cache, and temp remain project-local.
- No ASR implementation is duplicated in Rust or TypeScript.

## Capability map

| Surface | Required capabilities |
| --- | --- |
| Transcription Studio | Drag/drop and browse audio/video, engine/model selection, searchable multi-language selection, overwrite/cache settings, live stage progress, live console, cancel, output path, open transcript folder |
| Transcript Library | List files under Transcripts, select and read timestamped output in-app, open folder, delete managed transcript, refresh |
| Live Transcription | Microphone, system output, and visible application capture; source refresh; model and searchable language selection; start/stop/save; live notes; warning about model memory and permissions |
| Hardware & Pipeline | Friendly CPU/GPU names, accelerator status, CPU/RAM/GPU/VRAM telemetry, pipeline stage tracker, idle/active state, backend diagnostics |
| Console Logs | Backend messages and errors remain available even when the main studio view is compact |
| App shell | Sidebar collapse, accessible keyboard navigation, native browse dialogs, graceful fallback when the Python backend is unavailable |

## Design direction

- Background: near-black blue-violet surfaces with quiet atmospheric depth.
- Accent: pink is a small signal color for focus, selection, progress, and
  identity—not a large filled navigation block.
- Secondary signals: cyan for links/active hardware, yellow for warnings,
  green for healthy completion, red for errors.
- Motion: opacity/translate/layout transitions only; no continuous expensive
  blur or canvas effects; respect reduced-motion preferences.
- Density: compact desktop workspace with clear hierarchy, not a dashboard
  full of decorative cards.

## Bridge contract

The Python side exposes a JSON-lines service mode. Each request has an id and
an operation; responses and progress events carry the same id. The service
reuses the existing pipeline, live controller, language table, library,
hardware monitor, and project-local runtime paths. The Rust side keeps the
service process isolated so model memory is released when a job is cancelled or
finished.

## Release and cleanup contract

- Source, tests, documentation, assets, and launcher files remain at the repo
  root or in their existing logical folders.
- Build staging and release archives live under artifacts.
- Temporary PyInstaller work lives under artifacts/build.
- Local model/package caches remain project-local and ignored by Git.
- Old backup folders and redundant generated staging are removed only after
  their contents are verified as generated and no process is using them.

