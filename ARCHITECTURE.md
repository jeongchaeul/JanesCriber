# JanesCriber backend architecture

JanesCriber has one transcription pipeline shared by the GUI and command line.
The GUI collects settings and displays progress; it does not implement a second
version of media or Whisper processing.

```text
GUI or CLI
  -> TranscriptionConfig validation
  -> project-local runtime setup
  -> media validation and ffprobe probe
  -> collision-resistant transcript cache lookup
  -> cancellable FFmpeg audio extraction
  -> selected local ASR backend (Whisper, Qwen3-ASR, Vosk, or Wav2Vec2)
  -> safe accelerator loading with CPU fallback where supported
  -> CUDA/MPS execution or CPU fallback
  -> timestamp rendering
  -> atomic UTF-8 transcript publication
  -> guaranteed temporary job cleanup
```

## Runtime policy

- Windows setup chooses one Torch runtime: CPU on machines without NVIDIA, or
  CUDA when `nvidia-smi` is available.
- AMD and Intel systems remain functional through the CPU fallback.
- Qwen3-ASR is an optional file-transcription backend; its model weights stay
  in `.cache/qwen3-asr` and its official streaming path is not required by the
  desktop live-capture supervisor.
- Wav2Vec2 and Qwen3-ASR file recognition process bounded audio chunks so a
  long recording does not require the complete waveform in RAM at once.
- Whisper models, normalized audio, transcript cache, logs, and uv's package
  cache are intended to remain on the selected project drive.
- External commands receive argument arrays, never shell command strings.
- Temporary job directories are removed in a `finally` block.
- Cache files and final transcripts in `Transcripts/` are atomically published only after the
  complete payload has been written.

## Failure boundaries

Invalid settings fail before a job directory is created. Missing tools,
empty media, media without audio, corrupt caches, interrupted downloads,
missing optional Qwen packages, and failed model loads return actionable
errors. A CUDA load failure retries on CPU where possible so a machine remains
usable when its driver is unavailable.
