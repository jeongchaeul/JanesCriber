<div align="center">
  <img src="assets/icon.png" alt="JanesCriber logo" width="128">
  <h1>JanesCriber</h1>
  <p><strong>Private, local-first audio and video transcription</strong></p>
  <p>Janes Media Suite · v2.0.0 · Desktop release</p>
</div>

<br>

JanesCriber turns recordings, videos, microphone input, system audio, and
supported application audio into readable timestamped text. Your media is
processed on your machine instead of being uploaded to a transcription
service.

This is the transcription member of the Jane Media Suite. It is intended for
meetings, calls, interviews, lectures, videos, accessibility documentation,
and any other situation where searchable local notes matter.

> **v2.0.0 status:** Version 2.0.0 consolidates exclusively on the modern Tauri
> desktop interface, integrates self-contained packaging matching JaneConverter,
> bundles all required runtimes and tools, and adds cross-platform packaging
> support for Linux and macOS.

## Start here

### If you are a normal consumer

1. Open the [JanesCriber Releases page](https://github.com/janecerys/JanesCriber/releases).
2. Open the newest release and download the asset ending in
   `-Setup.exe`. Do **not** download the GitHub **Source code** archive and do
   **not** run `setup.bat` unless you specifically want the developer setup.
3. Run the installer and launch **JanesCriber Studio** from the Start menu or
   desktop shortcut. The installer already contains the app, local backend,
   and FFmpeg; Python, uv, and a separate FFmpeg installation are not needed.
4. Before downloading a model, open **Settings → Local-first storage → Choose
   folder** and select a writable location such as `D:\JanesCriberData`.
   Relaunch Studio when it asks. This keeps transcripts, models, temporary
   audio, and logs on the drive you choose instead of letting them accumulate
   on C:.
5. Choose **Transcription Studio**, select an audio or video file, choose a
   model and language, then press **Transcribe**. Results appear in the
   **Transcript Library** and in the selected data folder's `Transcripts`
   directory.

The one-file consumer installer uses a universal CPU-safe runtime so it can
start reliably across NVIDIA, AMD, Intel, Apple, and CPU-only machines. It
does not bundle every vendor's multi-gigabyte accelerator runtime. For
hardware-tuned CUDA, DirectML, ROCm, XPU, Qwen3-ASR, or specialist developer
setups, use the developer path below.

Studio checks the official GitHub Releases page when it starts and also has a
manual **Settings → Updates → Check for updates** action. It only treats a
published release with a `-Setup.exe` asset as installable. When an update is
found, Studio opens the official release page so the user can verify and run
the new installer; it never replaces application files or local data silently.

If Windows displays a SmartScreen warning, verify that the file came from the
official release page and that its SHA-256 value matches the accompanying
`.sha256` asset before choosing **More info → Run anyway**. The installer is
currently unsigned.

### If you downloaded a release ZIP

1. Extract the complete ZIP to a folder on the drive where you want JanesCriber
   to keep its data. A location such as `D:\Apps\JanesCriber` is fine.
2. Keep every file and folder from the archive together. Do not run the EXE
   directly from inside the ZIP.
3. Open `JanesCriber.exe` or `JanesCriberStudio.exe` to launch **JanesCriber Studio**.
4. The first time you select a model, JanesCriber downloads that model into
   the local `.cache` folder. This requires internet access once; the actual
   transcription remains local.

The portable release contains the packaged Python runtime, JanesCriber Studio,
FFmpeg, and the dependency notices. It does not require a separate Python
installation. The selected ASR model is downloaded on demand because bundling every model
would make the download unnecessarily large.

### If you are running from the Git repository

The supported Windows setup is:

```powershell
cd "D:\Documents\GitHub Repo\JanesCriber"
setup.bat
```

Before running setup, install these two machine-level prerequisites:

- **[uv](https://docs.astral.sh/uv/)** — creates and manages the private
  project Python environment.
- **FFmpeg** with both `ffmpeg.exe` and `ffprobe.exe` available on `PATH` —
  extracts a consistent speech stream from audio and video.

If Windows asks about microphone or audio capture permissions, allow them when
you want to use live transcription. The setup script does not silently install
system-wide FFmpeg or modify unrelated Python installations.

## What `setup.bat` does

The setup script is deliberately the normal entry point. It:

1. Runs from the JanesCriber folder so paths stay attached to the project.
2. Checks for `uv`, FFmpeg, and `ffprobe` and stops with a readable message if
   one is missing.
3. Detects the available hardware profile. NVIDIA CUDA is preferred when the
   NVIDIA runtime is visible; compatible Windows DirectX 12 hardware can use
   DirectML; unsupported or failed acceleration falls back to CPU.
4. Reuses a supported project-local Python environment when possible. If no
   supported Python 3.10–3.12 interpreter is available, it installs a managed
   interpreter under `.cache\python` instead of filling a system location.
5. Synchronizes the locked JanesCriber dependencies into `.venv`.
6. Installs the matching Torch runtime: CUDA for a detected NVIDIA runtime,
   DirectML when selected, or the CPU runtime as a safe fallback.
7. Rebuilds the small Windows launcher when the .NET compiler is available.
8. Leaves the application ready to launch. Model weights are still downloaded
   only when a model is first selected.

The installer keeps its uv cache, managed Python, temporary files, Torch cache,
Hugging Face cache, model files, logs, and transcripts beside the project as
much as the operating system and selected packages allow. This is why placing
the project on `D:` is recommended.

### Optional setup modes

```powershell
setup.bat                 # standard local setup; recommended
setup.bat qwen            # also install the optional Qwen3-ASR backend
setup.bat directml        # force the Windows DirectML compatibility backend
```

Do not combine `qwen` and `directml` in v1.0.0. The current optional package
matrix cannot use Qwen3-ASR with the DirectML Torch package. On a non-NVIDIA
Windows machine, plain `setup.bat` automatically chooses DirectML when it can
identify a physical DirectX 12 adapter; use `setup.bat qwen` when Qwen3-ASR is
more important, which keeps the standard Torch runtime instead.

## What happens on the first transcription

1. JanesCriber validates the selected media without moving or modifying the
   source file.
2. FFmpeg extracts a 16 kHz mono speech stream into the project `temp` folder.
3. The selected ASR model is loaded. The Console Logs and pipeline tracker
   show download, model-load, accelerator, and transcription progress.
4. The recognizer produces timestamped segments. Whisper also produces
   word-level timing information when available.
5. JanesCriber renders the selected export format and publishes it atomically
   in `Transcripts`. TXT is the default; SRT, VTT, and JSON are available for
   subtitle and integration workflows.
6. The file appears in **Transcript Library**, where it can be read, opened in
   Explorer, or deleted.

The default behavior avoids overwriting an existing transcript. Turn on
**Overwrite same-name transcript** in the UI or pass `--overwrite` when you
explicitly want replacement.

## Highlights

- **Audio and video input** — Anything the included or installed FFmpeg build
  can read, including MP3, WAV, M4A, FLAC, AAC, OGG, MP4, MKV, MOV, and WEBM.
- **Four local ASR families** — Whisper, Qwen3-ASR, Vosk/Kaldi, and Wav2Vec2.
- **Live transcription** — Capture a microphone, system output, or a visible
  application output source while it is happening.
- **GPU-first runtime selection** — Uses the best compatible runtime exposed by
  the installed packages, then falls back cleanly instead of assuming every
  computer has NVIDIA CUDA.
- **Searchable language selection** — Whisper's language catalog includes
  Tagalog/Filipino and can be searched by language name, native name, or code.
- **Transcript Library** — Manage and read generated transcripts inside the
  application without opening a separate viewer window.
- **Local export formats** — Keep the readable TXT default or generate SRT,
  VTT, and structured JSON segment files beside it in `Transcripts`.
- **Live console and pipeline tracker** — See what the worker is doing when a
  model takes time to load or a device needs a fallback.
- **Project-local data** — Outputs, model caches, scratch files, and logs are
  kept beside the program whenever possible.

## Choose the right ASR engine

| Engine | Best fit | Language behavior | Acceleration | Live capture |
| --- | --- | --- | --- | --- |
| **Whisper** | Best general quality, multilingual recordings, noisy audio | Broad multilingual catalog with searchable selection | CUDA/ROCm, Intel XPU, Apple MPS, DirectML, or CPU | Yes |
| **Qwen3-ASR** | Independent open-weight multilingual file transcription | Supported Qwen language and dialect catalog, including Filipino/Tagalog | CUDA/ROCm, Intel XPU, Apple MPS, or CPU | No, file transcription only in v1.0.0 |
| **Vosk / Kaldi** | Lightweight, responsive, long live sessions | One downloaded Vosk language model at a time | CPU in the standard package | Yes |
| **Wav2Vec2** | Independent local English-focused option | English-focused | CUDA/ROCm, Intel XPU, Apple MPS, DirectML, or CPU | Yes |

### Whisper

Whisper is the default quality-oriented choice for mixed languages, noisy
recordings, and general use. `tiny` and `base` are the most practical live
choices. `small`, `turbo`, and `large-v3` can produce better results but need
more memory and can take longer to load.

### Qwen3-ASR

Qwen3-ASR is an optional independent open-weight ASR family. It is useful when
you want a non-OpenAI model, especially for supported multilingual file
recordings. Install it with `setup.bat qwen`; it is not enabled by the normal
setup because it adds a substantial optional package and model download.

Qwen3-ASR is intentionally file-only in this release. Use Whisper, Vosk, or
Wav2Vec2 for live sessions.

### Vosk / Kaldi

Vosk is the lightweight live option. It starts quickly and is a good choice for
long sessions or machines with limited memory. Its accuracy depends heavily on
the selected Vosk model and language. Models are downloaded to
`.cache\vosk` only when selected.

### Wav2Vec2

Wav2Vec2 provides another local English-focused path. It uses the same device
selection and CPU-retry behavior as the rest of the Torch-backed pipeline, but
its bundled model is not a replacement for Whisper's multilingual catalog.

## GPU and CPU behavior

JanesCriber does not hard-code one graphics vendor. At runtime it checks the
available Torch device backends and uses the first usable accelerator in this
order:

1. NVIDIA CUDA or AMD ROCm/HIP through Torch's shared `cuda` device API.
2. Intel XPU when the Intel extension is installed and usable.
3. Apple MPS on Apple Silicon/macOS builds.
4. Optional Windows DirectML for compatible DirectX 12 GPUs.
5. CPU fallback.

The exact result depends on the operating system, GPU driver, Torch wheel, and
model backend. A GPU being present does not guarantee that every model can run
on it. If model initialization fails on an accelerator, JanesCriber reports
the failure and retries on CPU rather than silently losing the job.

| Machine | Recommended path |
| --- | --- |
| NVIDIA GPU | Run normal `setup.bat`; CUDA is selected when `nvidia-smi` is available. |
| AMD GPU on Linux | Install a Torch ROCm build appropriate for the machine. |
| AMD or Intel GPU on Windows | Normal setup can select DirectML; `setup.bat directml` forces it. |
| Intel GPU with XPU support | Use the matching Intel Torch/XPU environment when available. |
| Apple Silicon | Use a native macOS environment with the MPS-capable Torch build. |
| No usable GPU | Run the CPU runtime; choose `tiny`, `base`, or Vosk for responsiveness. |

The Windows DirectML path is a compatibility path, not a promise that every
DirectX device will perform like native CUDA. Native runtimes are preferred
when a stable, model-compatible build exists.

## Live transcription

Open **Live Transcription** and choose one of these sources:

- **Microphone** — a physical or virtual input device.
- **System output** — audio currently playing through a speaker or headset.
- **Application output** — a visible application window that is currently
  producing audio. Background processes and hidden windows are intentionally
  not shown.

For a first live test, use Whisper `tiny` or `base`, or Vosk. Large Whisper
models are poor choices for a long live session on a memory-limited computer.
Choose the source that is actually producing audio, refresh the source list if
you opened a new app, and check Windows microphone permissions. Application
output capture requires the optional Windows ProcTap package included by the
normal Windows dependency setup.

Live sessions continuously write timestamped text into `Transcripts` and make
the finished file available in **Transcript Library**. Stop and save before
closing the application so the final segment is flushed.

If recognition cannot keep up with the selected capture source, JanesCriber
keeps the audio queue bounded to protect memory and reports the number of
dropped buffered chunks in the live notes and console. Use Whisper `tiny`,
`base`, or Vosk for long sessions when this warning appears.

## Storage and C: drive protection

When the project or portable folder is on `D:`, JanesCriber uses these paths:

```text
JanesCriber\
├─ Transcripts\             Completed .txt/.srt/.vtt/.json files, including live sessions
├─ .cache\
│  ├─ whisper\              Whisper model weights
│  ├─ vosk\                 Vosk/Kaldi model files
│  ├─ wav2vec2\             Wav2Vec2 model files
│  ├─ qwen3-asr\            Optional Qwen3-ASR model files
│  ├─ huggingface\          Hugging Face downloads
│  ├─ torch\                Torch cache
│  ├─ uv-cache\             uv package cache
│  ├─ python\               Managed Python, if setup had to install it
│  └─ logs\                 Local diagnostic logs
└─ temp\                    Temporary normalized audio and working files
```

The source media is never moved or modified. Transcript output is not written
beside the source media; it is written to the program's `Transcripts` folder.
On first use, model downloads can be large. Delete only unused model folders
from `.cache` when you need space; JanesCriber will download a selected model
again if it is needed later.

The operating system, GPU drivers, browser downloads, and developer tools may
still use C:. JanesCriber controls its own caches and temporary paths, not
every cache created by Windows or third-party package managers.

## Desktop Studio and CLI

JanesCriber provides a modern native desktop interface along with direct command-line access:

- **JanesCriber Studio** — the native Tauri/React interface with JaneConverter-level polish, customizable theme colors, compact workspace layout, transcript library, real-time hardware telemetry, live capture, and console logs.
- **CLI Mode** — direct terminal execution for script automation and headless environments without a graphical surface.

## Command line

The backend can be used without a desktop window:

```powershell
.\.venv\Scripts\python.exe -m janescriber path\to\recording.mp4
.\.venv\Scripts\python.exe -m janescriber path\to\recording.mp4 --engine whisper --model turbo
.\.venv\Scripts\python.exe -m janescriber path\to\recording.mp4 --engine vosk --model en-us-small
.\.venv\Scripts\python.exe -m janescriber path\to\recording.mp4 --engine wav2vec2 --model wav2vec2-base-960h
.\.venv\Scripts\python.exe -m janescriber path\to\recording.mp4 --overwrite
```

The output is saved in `Transcripts`. Use the application for the searchable
multi-language picker, live capture sources, pipeline display, and library
actions.

Use the project interpreter directly after setup. A plain `uv run` can ask uv
to reconcile Whisper's transitive Torch dependency with a generic PyPI wheel,
which may replace a hardware-specific Torch installation. If you do use uv,
prefer `uv run --no-sync` after setup.

## Building a release

### Portable package

From a prepared Windows checkout:

```powershell
.\build_release.ps1
```

The script builds the self-contained backend runtime, bundles FFmpeg, copies available
dependency notices into `licenses`, includes JanesCriber Studio, creates a ZIP under `artifacts\releases`, and writes a SHA-256 file.
The default package deliberately excludes the optional Qwen3-ASR package even
when it happens to be installed in the developer environment. Include it only
when you are making a larger specialist bundle:

```powershell
.\build_release.ps1 -WithQwen
```

The release is unsigned unless a certificate is supplied:

```powershell
.\build_release.ps1 -CertificatePath C:\path\to\signing-certificate.pfx
```

### One consumer installer

The normal consumer build produces one NSIS setup executable containing the
Studio UI, a universal CPU-safe packaged Python backend, and the local FFmpeg
runtime. This keeps the installer below Windows' single-file NSIS size limit
while preserving a reliable fallback on machines with NVIDIA, AMD, Intel,
Apple, or no usable accelerator:

```powershell
.\build_consumer_installer.ps1
```

The output is written to `artifacts\releases` as:

```text
JanesCriber-2.0.0-windows-x64-setup.exe
JanesCriber-2.0.0-windows-x64-portable.zip
```

The packaging script validates that the installer, manifest version, bundled
FFmpeg declaration, and SHA-256 files all match before it reports success.
The repository also checks that the Python, npm, Tauri, and Cargo version
metadata stay consistent.

Qwen3-ASR and hardware-specific CUDA/ROCm/XPU/DirectML package variants remain
opt-in through the developer build path. Use `setup.bat` when you want the
largest hardware-tuned runtime and model choices; use the one-file installer
when you want the simplest universal installation. The existing `setup.bat`
path is the developer/nerdy safety net. A consumer does not need Python, uv,
FFmpeg, or the repository checkout after installing the setup executable.

### JanesCriber Studio

Studio is built with Tauri 2, React, TypeScript, Tailwind CSS, Framer Motion,
and Rust native bindings. Building the native UI requires Node.js/npm and the
Rust toolchain:

```powershell
.\build_release.ps1
.\build_desktop_ui.ps1
```

For a single consumer artifact, prefer `build_consumer_installer.ps1` above;
the two commands here are useful when developing Studio independently.

The desktop build script installs the locked frontend dependencies, builds the
frontend, then creates the native Tauri bundle. Use
`-SkipLegacyRuntime` only for a frontend-only development build; a distributable
Studio release should include the packaged backend.

## Privacy, network use, and licensing

- Audio and video are transcribed locally by the selected model.
- JanesCriber does not send recordings to an AI API.
- Network access is used for setup dependencies, optional model downloads, and
  model/runtime caches when a file is not already present.
- Model and dependency licenses are separate from the JanesCriber project
  license. Review the license for each selected model before redistributing it.
- Portable builds include dependency notices when the source metadata exposes
  them. Keep those notices with redistributed builds.

## Troubleshooting

### Setup says `uv`, FFmpeg, or `ffprobe` is missing

Install the missing prerequisite, open a new PowerShell or Command Prompt so
`PATH` refreshes, and run `setup.bat` again. The complete FFmpeg package must
provide both `ffmpeg.exe` and `ffprobe.exe`.

### The model appears to be stuck loading

The first load includes disk access, model initialization, and possibly a GPU
memory transfer. Watch **Console Logs** and **Hardware & Pipeline**. Large
models can take minutes on some machines. Try Whisper `tiny` or `base` to
separate a slow model load from a broken audio pipeline.

### The expected GPU is not being used

Check the Hardware & Pipeline page and the Console Logs. The installed Torch
runtime must match the device family: CUDA/ROCm, Intel XPU, Apple MPS, or
DirectML. A driver, model, or memory problem can cause a safe CPU retry. CPU
fallback is slower but is an intentional compatibility behavior.

### Live transcription has no text

Confirm that the selected source is producing audio. For a microphone, check
Windows privacy permissions and the selected input. For system output, check
the active speaker or headset. For application output, select a visible window
that is playing sound and refresh the source list. If the console reports that
ProcTap or an audio package is missing, run `setup.bat` again.

### Live transcription reports a full audio buffer

The recognizer is slower than the selected audio source. This is a protective
warning rather than an unbounded-memory failure. Stop and save the session,
then retry with Whisper `tiny`/`base`, Vosk, a shorter session, or a less
expensive capture source.

### C: is filling up

Place the checkout or portable folder on the desired drive before setup and
model downloads. Inspect `.cache` and remove unused model directories. Do not
delete the active `.venv` or a model currently being used. System-level Python,
uv, GPU-driver, and Windows caches are outside JanesCriber's project-local
controls.

### The program opens but Studio is unavailable

Run `npm.cmd run tauri:build -- --no-bundle` inside `desktop-ui` (or `build_desktop_ui.ps1`) to compile the Studio executable beside the project root.

## Verification

Run the tests from the project folder with the project interpreter:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q src
```

The suite covers output naming, timestamp formatting, cache validation, media
handling, cancellation, cleanup, language selection, live-capture helpers,
hardware selection, library behavior, launcher preferences, and local runtime
paths, export formats, release artifacts, version consistency, and live
backpressure diagnostics. A real audio/video smoke test should still be performed on the target
machine because GPU drivers, codecs, permissions, and audio devices vary.

Every push and pull request also runs the Windows quality-gate workflow for
Python tests/compile checks, version consistency, the frontend tests/build,
production dependency audit, and Tauri/Rust source compilation.

## Project documentation

- [Architecture](ARCHITECTURE.md) — backend boundaries and pipeline structure.
- [Release notes](CHANGELOG.md) — user-facing v2.0.0 changes.
- [Release plan](RELEASE_PLAN.md) — follow-up hardening and distribution work.
- [Desktop UI parity](docs/desktop-ui-parity.md) — legacy and Studio feature
  coverage.
- [Desktop UI specification](docs/desktop-ui-spec.md) — Studio design and
  behavior contract.

## Reporting an issue

Open an issue with:

- Windows version and CPU/GPU summary;
- selected engine, model, and language;
- whether the issue involved a file, microphone, system output, or application
  output;
- the relevant Console Logs text; and
- steps that reproduce the problem.

Please do not attach private recordings or transcripts unless they have been
sanitized and you have permission to share them.
