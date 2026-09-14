# JanesCriber

JanesCriber is the transcription member of the Jane media suite. It turns
spoken audio from audio or video files into a UTF-8 `.txt` transcript with
timestamps, while keeping the source file untouched.

## What it does

- Reads any audio/video container supported by FFmpeg (`.mp3`, `.wav`, `.m4a`,
  `.flac`, `.aac`, `.ogg`, `.mp4`, `.mkv`, `.mov`, `.webm`, and more).
- Extracts a normalized 16 kHz mono stream for the selected ASR engine.
- Uses NVIDIA CUDA/FP16 when available, Apple MPS when available, and a tuned
  CPU fallback otherwise.
- Offers two local ASR engines: **Whisper**, developed by OpenAI and run locally,
  and **Vosk / Kaldi**, an independent offline recognizer that does not use an
  OpenAI model or cloud API.
- Produces one timestamped text file in the `Transcripts` folder inside the
  example `interview.mp4` → `JanesCriber\Transcripts\interview.txt`.
- Caches transcripts by source fingerprint, model, and language so reruns do
  not need to invoke Whisper again.

## Storage policy

JanesCriber deliberately keeps working data under the project folder:

```text
JanesCriber/
  Transcripts/          generated transcript text files
  .cache/whisper/       downloaded Whisper models
  .cache/vosk/          downloaded Vosk/Kaldi models
  .cache/wav2vec2/      downloaded Wav2Vec2 models
  .cache/transcripts/   validated transcript cache
  temp/                 short-lived normalized audio
```

The generated `.txt` file is always written to `JanesCriber\\Transcripts`.
Live transcripts use the same folder and appear in Transcript Library as soon
as they are saved. On startup, legacy root-level `.txt` outputs are moved there
automatically with collision-safe names.
Set up and run the project from a drive with enough free space; Whisper models
are large, especially `large-v3` and `turbo`. Vosk models are downloaded only
when that engine is selected and are stored in `.cache\vosk` on the project
drive.

## ASR engines

Whisper is the quality-oriented option and supports the broad multilingual
language picker, GPU acceleration, and mixed-language prompts. Vosk / Kaldi is
an independent local option for users who prefer a lightweight offline engine.
It uses one downloadable language model at a time, runs on the CPU, and may be
less accurate than Whisper on difficult audio. The official Vosk model catalog
is available at https://alphacephei.com/vosk/models; model licenses vary and
are shown in the model metadata.
Wav2Vec2 is an additional English-focused local model from Meta AI Research
([model card](https://huggingface.co/facebook/wav2vec2-base-960h)) that uses the
existing Torch runtime and takes advantage of NVIDIA CUDA when available; it
falls back to CPU when CUDA is unavailable. Its model weights are licensed
under Apache-2.0.

## Live transcription sources

The Live Transcription tab can capture:

- **Microphone** — a physical or virtual input device.
- **System output** — the audio mix playing through a selected speaker or headset using WASAPI loopback.
- **Application output** — one visible application window on supported Windows 10/11 systems. The picker shows friendly app/window names; process IDs and background processes stay hidden.

Use **Application output** when several apps are playing audio and only one should be transcribed. System output captures everything using the selected speaker endpoint. A selected app can be silent until it begins playing audio.

The language dialog contains the complete Whisper multilingual catalog, including Tagalog, and can be searched by English name, native name, or language code. Multiple languages can be selected together for mixed or code-switched speech.

For live transcription, use `tiny` or `base` for the best balance of speed,
memory use, and responsiveness. `small` and `turbo` need substantially more
RAM and are better suited to short sessions on machines with plenty of memory.

## Portable Windows release

Extract the release ZIP to a folder on a drive with enough free space and
double-click `JanesCriber.exe`. Python, Torch, Transformers, and FFmpeg are bundled, so a
consumer machine does not need Python, uv, or a separate FFmpeg installation.
The first run downloads the selected ASR model into `.cache\\whisper` or
`.cache\\vosk` on the same drive. Model downloads can be large; keep the application on a drive
with sufficient free space.

The bundled build uses NVIDIA CUDA when the installed driver supports the
included Torch runtime and falls back to CPU on AMD, Intel, and CPU-only
systems. The application remains Windows-only in this release.

## Developer setup

For a source checkout, install FFmpeg and ensure both `ffmpeg` and `ffprobe`
work in a terminal. Then install [uv](https://docs.astral.sh/uv/) and run
`setup.bat`:

```text
JanesCriber/
  setup.bat
```

Setup verifies Python 3.10, 3.11, or 3.12, FFmpeg, and FFprobe. It stores uv's
wheel cache in `.uv-cache` beside the project, then chooses a CPU Torch runtime
on CPU-only systems or a CUDA Torch runtime when NVIDIA is detected. AMD and
Intel systems remain supported through the CPU fallback. Close any running
JanesCriber window before running setup so Windows can safely update the runtime
files.

For a direct developer launch after setup:

```powershell
uv run python -m janescriber --gui
```

The first run downloads the selected Whisper, Vosk, or Wav2Vec2 model into its
matching `.cache` folder. `turbo` is the default Whisper balance of speed and accuracy.
Use `large-v3` for the strongest accuracy, or `small`, `base`, and `tiny` on
lower-spec systems. Vosk model IDs are available in the engine selector.

## Command line

```powershell
uv run python -m janescriber "D:\Media\interview.mp4"
uv run python -m janescriber "D:\Media\meeting.m4a" --model large-v3 --language en
uv run python -m janescriber "D:\Media\meeting.m4a" --overwrite
```

Run `uv run python -m janescriber --help` for all options.

## Privacy

Transcription is local. JanesCriber does not upload media or require a cloud
API key. Network access is only needed to download a selected Whisper, Vosk, or
Wav2Vec2 model the first time it is used in the portable release. Dependency license texts are
included in the release `licenses` folder.

## Verification

```powershell
uv run pytest -q
```

The current tests cover timestamp rendering, cache validation, safe naming,
media validation, cancellation, pipeline cleanup, language handling, and
app-local runtime paths. A real GPU/FFmpeg transcription should still be
smoke-tested on the target Windows machine because those depend on installed
drivers and media codecs.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the backend boundaries.
