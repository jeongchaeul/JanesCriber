<div align="center">
  <img src="assets/icon.png" alt="JanesCriber logo" width="128">
  <h1>JanesCriber</h1>
  <p><strong>Local-first audio and video transcription for Windows</strong></p>
  <p>Private by default · GPU-aware · Timestamped documentation</p>
</div>

<br>

JanesCriber is the transcription member of the Jane Media Suite. It turns
recordings, videos, microphone input, system audio, and supported application
audio into readable timestamped text—without sending your media to a cloud
service.

The project is designed for people who need dependable documentation from
meetings, calls, interviews, lectures, videos, and everyday conversations.

> **Project status:** JanesCriber is under active development. The portable
> Windows build is usable, but hardware-specific and long-session testing is
> still part of the release process.

## Highlights

- **Audio and video files** — Open any format that the bundled FFmpeg build can
  read, including MP3, WAV, M4A, FLAC, AAC, OGG, MP4, MKV, MOV, and WEBM.
- **Three local ASR engines** — Choose between Whisper, Vosk/Kaldi, and
  Wav2Vec2 depending on your priorities for accuracy, speed, language coverage,
  and memory use.
- **Live transcription** — Capture a microphone, system output, or a visible
  application window while it is happening.
- **GPU acceleration when available** — NVIDIA CUDA/FP16 and Apple MPS are
  detected automatically; AMD, Intel, and CPU-only machines use the CPU path.
- **Searchable language picker** — Whisper supports its broad multilingual
  catalog, including Tagalog/Filipino, with search by language name, native name,
  or code.
- **Transcript Library** — Browse saved transcripts, open their containing
  folder, delete files, and read transcript text inside the application.
- **Readable output** — Timestamps are rendered as their own lines, followed by
  the corresponding transcript text.
- **Recovery-friendly pipeline** — Progress, hardware state, console messages,
  cancellation, cleanup, and failures are surfaced instead of disappearing
  behind a permanently busy screen.
- **Project-local storage** — Generated transcripts, model downloads, caches,
  and temporary media stay beside the application whenever possible.

## Example output

```text
[00:00:00.660 --> 00:00:03.640]
>Hey man, so I called because I wanted to talk to you about something.

[00:00:05.420 --> 00:00:10.640]
>I wanted to give you the full details before I head over there.
```

Each completed file is written as UTF-8 text in the `Transcripts` folder.

## Choose the right engine

| Engine | Best for | Languages | Acceleration | Live capture |
| --- | --- | --- | --- | --- |
| **Whisper (OpenAI)** | Highest-quality general transcription and multilingual audio | Broad multilingual catalog | NVIDIA CUDA/FP16, Apple MPS, or CPU | Yes |
| **Vosk / Kaldi** | Lightweight, offline transcription and long live sessions | One downloaded language model at a time | CPU in the standard Vosk package | Yes |
| **Wav2Vec2** | An independent local English-focused model with optional CUDA | English-focused | NVIDIA CUDA when available, otherwise CPU | Yes |

### Whisper

Whisper is the quality-oriented default for mixed, multilingual, noisy, or
general-purpose recordings. Larger models can improve accuracy, but require
more memory and take longer to load.

### Vosk / Kaldi

Vosk is an independent offline recognizer and does not use an OpenAI model or a
cloud API. It is a practical choice for responsive, memory-conscious live
transcription. Its accuracy depends heavily on the selected language model and
recording conditions. Model licenses vary; JanesCriber records the model
metadata and license information beside each downloaded model.

Browse the official Vosk model catalog at
[alphacephei.com/vosk/models](https://alphacephei.com/vosk/models).

### Wav2Vec2

Wav2Vec2 is an additional local model from Meta AI Research. The bundled
integration uses the existing Torch runtime and takes advantage of NVIDIA CUDA
when available, with a CPU fallback. The current model is English-focused and
is licensed under Apache-2.0.

See the [Wav2Vec2 model card](https://huggingface.co/facebook/wav2vec2-base-960h)
for its model details and limitations.

## Live transcription

Open **Live Transcription** to document speech as it happens. Select a capture
mode before starting:

- **Microphone** — A physical or virtual input device.
- **System output** — The audio mix playing through a selected speaker or
  headset using Windows audio loopback.
- **Application output** — One visible application window, useful when several
  applications are producing audio at the same time.

The application picker shows friendly names for visible windows. Background
processes and raw task-manager PID lists are intentionally hidden. A selected
application can remain quiet until that application begins playing audio.

### Live-session recommendations

- Start with **Whisper `tiny` or `base`** for the best balance of responsiveness,
  memory use, and accuracy.
- Use **Vosk** when a lightweight, long-running session is more important than
  maximum recognition quality.
- Use **Wav2Vec2** for an independent local English option when CUDA is
  available; its live mode uses short rolling recognition windows.
- Avoid **Whisper `small`, `turbo`, or `large-v3`** for long live sessions on
  machines with limited RAM. These models can take substantially longer to load
  and may make the interface less responsive.
- For application capture, choose a visible top-level app window and confirm
  that the app is actually producing audio. The optional ProcTap package is
  required by the Windows application-output backend.

Live transcripts are saved into `Transcripts` and appear in **Transcript
Library** after they are finalized.

## Where JanesCriber stores data

JanesCriber follows a local-first, D-drive-friendly layout:

```text
JanesCriber/
├─ JanesCriber.exe              Portable application entry point
├─ Transcripts/                 Completed and live transcript files
├─ .cache/
│  ├─ whisper/                  Downloaded Whisper models
│  ├─ vosk/                     Downloaded Vosk/Kaldi models
│  ├─ wav2vec2/                 Downloaded Wav2Vec2 models
│  └─ transcripts/              Validated transcript cache
└─ temp/                        Short-lived normalized audio files
```

The application does not intentionally place transcript output in the Windows
user profile or redirect it to `C:`. Keep the project and portable release on a
drive with enough free space, especially when using large Whisper models.

Windows and developer tooling can still maintain their own system-managed files
outside this folder. The portable application itself keeps its models, cache,
temporary work, and output beside the program.

## Portable Windows release

The portable build is the simplest way to run JanesCriber on a Windows machine.

1. Download the release ZIP from the repository's Releases page.
2. Extract it to a permanent folder on the drive where you want the models and
   transcripts stored.
3. Launch `JanesCriber.exe`.
4. Choose a media file, select an engine and language, then start transcription.

Python, Torch, Transformers, and FFmpeg are bundled in the portable release, so
the target machine does not need Python, `uv`, or a separate FFmpeg installation.
The first use of a selected model downloads its weights into the matching
`.cache` folder. Model downloads can be large and require an internet connection
only for that initial download.

The current portable release targets Windows. NVIDIA acceleration requires a
compatible installed driver; machines with AMD, Intel, or no supported GPU
remain usable through the CPU fallback.

## Developer setup

### Requirements

- Windows 10 or Windows 11
- Python 3.10, 3.11, or 3.12
- FFmpeg and FFprobe available to the source checkout
- [uv](https://docs.astral.sh/uv/)

Clone or copy the repository to the drive where you want its environment and
cache to live, then run:

```bat
setup.bat
```

The setup script verifies Python and FFmpeg, keeps uv's wheel cache beside the
project, and selects a CPU Torch runtime or an NVIDIA CUDA runtime based on the
machine. Close any running JanesCriber window before running setup so Windows
can update the environment safely.

Launch the desktop application with:

```powershell
uv run python -m janescriber --gui
```

The first use of Whisper, Vosk, or Wav2Vec2 downloads the selected model into
the corresponding project-local cache.

## Command-line use

JanesCriber can also transcribe a file without opening the desktop interface:

```powershell
uv run python -m janescriber "D:\Media\interview.mp4"
uv run python -m janescriber "D:\Media\meeting.m4a" --model large-v3 --language en
uv run python -m janescriber "D:\Media\meeting.m4a" --overwrite
```

Run the help command to see the options available in the installed version:

```powershell
uv run python -m janescriber --help
```

## Build a portable executable

After completing source setup, build the Windows bundle with:

```powershell
.\build_release.ps1
```

The output is placed in `dist\`. The build script creates the portable folder,
copies the required runtime assets, verifies important bundled components, and
can create a release ZIP. The executable is unsigned by default; provide a code
signing certificate to the build script when preparing a trusted public release.

Wav2Vec2 model weights are intentionally downloaded on demand rather than
bundled into the executable, keeping the release smaller and allowing users to
choose whether they need that engine.

## Privacy and network behavior

JanesCriber is local-first:

- Media is transcribed on the local machine.
- No cloud API key is required for the local engines.
- Media and transcript text are not uploaded by the application.
- Network access is used to download a selected model the first time it is
  needed in a source or portable installation.
- Downloaded models and caches remain in the project-local `.cache` directory.

Review the license and usage terms of each selected model. Dependency license
texts are included in the portable release's `licenses` folder.

## Troubleshooting

### The model appears to be loading for a long time

The first model load includes disk access, model initialization, and—when
available—transfer into GPU memory. Large models can take several minutes on
some machines. The Console Logs and pipeline tracker show the active stage. For
live use, switch to `tiny`, `base`, or Vosk if the machine has limited memory.

### CUDA is not available

JanesCriber continues with CPU transcription. Check the Hardware & Pipeline tab
and confirm that the installed NVIDIA driver is compatible with the bundled Torch
runtime. CUDA is an acceleration path, not a requirement for using the program.

### Live transcription cannot start

Confirm that the selected source exists and is producing audio. For microphone
capture, check Windows microphone permissions and select the correct input
device. For system output, select an active speaker or headset. For application
output, refresh the visible application list and select a window that is playing
audio. Run `setup.bat` again if an optional audio package is missing.

### The C: drive is filling up

Keep the portable folder or source checkout on the desired drive and allow the
first model download to finish there. Remove unused models from the matching
`.cache` folder only when you no longer need them. Developer environments and
package managers may have separate caches that are outside JanesCriber's control.

### A transcript already exists

The default behavior preserves the existing text file. Enable overwrite in the
desktop interface or pass `--overwrite` on the command line when replacement is
intentional.

## Verification

Run the automated test suite from the project folder:

```powershell
uv run pytest -q
```

The tests cover timestamp formatting, cache validation, safe output naming,
media validation, cancellation, pipeline cleanup, language handling, live
capture helpers, and application-local runtime paths. A real GPU/FFmpeg
transcription should still be smoke-tested on the target Windows machine because
drivers, audio devices, and media codecs vary between systems.

## Project documentation

- [Architecture](ARCHITECTURE.md) — Backend boundaries and pipeline structure.
- [Release plan](RELEASE_PLAN.md) — Remaining release-readiness work and gates.

## Feedback

If you find a transcription, capture, packaging, or hardware compatibility
problem, open an issue with:

- Windows version and hardware summary;
- selected engine, model, and language;
- whether the problem occurred with a file, microphone, system output, or
  application output;
- the relevant Console Logs text; and
- steps that reproduce the problem.

Please avoid attaching private recordings or transcripts unless they have been
sanitized.
