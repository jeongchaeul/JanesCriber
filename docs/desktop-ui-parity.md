# JanesCriber Studio and Legacy Launcher Parity

The native desktop surface is a client of the existing Python engine. This
table is the release gate for the two launchers.

| Legacy launcher capability | JanesCriber Studio |
| --- | --- |
| Choose audio or video through Browse | Native file dialog plus drag-and-drop zone |
| FFmpeg accepts the same audio/video source types | Same Python media validation and extraction pipeline |
| Whisper model choices | Whisper, Qwen3-ASR, Vosk/Kaldi, and Wav2Vec2 catalogs |
| Language presets and multi-language selection | Searchable multi-select using the shared language catalog, including Tagalog/Filipino |
| Overwrite and transcript-cache settings | Same settings forwarded to the Python pipeline |
| Six-stage progress tracker | Same six stages with live progress and status text |
| Console Logs view | Embedded live console plus full Console Logs page |
| Output in the project Transcripts folder | Same path returned by the Python runtime service |
| Transcript Library list, read, open, and delete | Same managed-folder actions with an in-app timestamp-aware viewer |
| Microphone capture | Live Transcription microphone mode |
| System output capture | Live Transcription system-output mode |
| Visible application output capture | Live Transcription application-output mode with friendly visible-window cards |
| Live model and language settings | Same supported live engines, model warnings, and language picker |
| Hardware and pipeline monitor | Friendly hardware names, CPU/RAM/GPU/VRAM telemetry, and tracker |
| Project-local cache and scratch paths | Same D-drive-friendly runtime paths, exposed in Hardware & Pipeline |
| Legacy Python Tk launcher | Preserved as the fallback launcher and backend source of truth |
| Cancel isolated work | Rust supervises the bridge; Python transcription and live workers remain isolated |

The native shell deliberately does not reimplement ASR. That keeps model
behavior, cancellation, output formatting, and future engine improvements
consistent between both launchers.

