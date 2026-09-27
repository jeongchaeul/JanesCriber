<div align="center">
  <img src="assets/icon.png" alt="JanesCriber logo" width="128">
  <h1>JanesCriber</h1>
  <p><strong>Fast, private, 100% offline audio & video transcription on your own machine.</strong></p>
  <p>Zero cloud APIs · Zero data leaks · Zero terminal needed · Janes Media Suite</p>
  <p>
    <a href="https://github.com/jeongchaeul/JanesCriber/releases/latest"><img src="https://img.shields.io/badge/version-2.0.0-blue.svg" alt="Version 2.0.0"></a>
    <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg" alt="Platforms">
    <img src="https://img.shields.io/badge/engine-Whisper%20%7C%20Vosk%20%7C%20Wav2Vec2-orange.svg" alt="Engines">
    <img src="https://img.shields.io/badge/privacy-100%25%20Local-success.svg" alt="100% Local">
  </p>
</div>

<br>

**JanesCriber** turns audio and video recordings, live microphone input, and system audio into readable, timestamped text. Everything runs directly on your computer's CPU or GPU. Nothing is ever uploaded to a remote server or AI cloud.

---

## ⚡ Quick Start (Zero Terminal, Zero Prerequisites)

### 1. Download & Install
1. Open the **[Releases](https://github.com/jeongchaeul/JanesCriber/releases/latest)** page.
2. Download **`JanesCriber-2.0.0-windows-x64-setup.exe`** (or download the portable `.zip` if you prefer a no-install folder).
3. Run the installer and launch **JanesCriber Studio**. *(Python, FFmpeg, and PyTorch runtimes are already bundled internally — no extra downloads needed).*

### 2. Drag, Drop & Transcribe
1. **Drag and drop** any audio or video file directly into JanesCriber.
2. Pick your model (or leave on the **Whisper Turbo** default).
3. Click **Transcribe** (or press `Ctrl+Enter`).
4. View your transcript in the app or export to plain text (`.txt`), subtitles (`.srt`, `.vtt`), or JSON.

---

## 🎯 Model & Engine Guide

Choose the model that matches your hardware and workload. Everything runs offline:

| Model | Engine | Memory (VRAM / RAM) | Speed | Accuracy | Best For | Recommended for Live Capture? |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **Whisper Tiny** | Whisper | ~1 GB | ⚡⚡⚡ Instant | Good | Quick drafts, low-spec PCs, fast note-taking | ✅ **Yes — Ideal** (Zero lag) |
| **Whisper Base** | Whisper | ~1 GB | ⚡⚡ Very Fast | Very Good | Everyday meetings, podcasts, voice memos | ✅ **Yes — Balanced** |
| **Whisper Small** | Whisper | ~2 GB | ⚡ Fast | High | Accented speech, technical jargon, interviews | ⚠️ GPU Recommended |
| **Whisper Medium** | Whisper | ~5 GB | ⏱️ Moderate | Very High | Multi-speaker lectures, music, noisy audio | ❌ File Only (High Latency) |
| **Whisper Turbo** | Whisper | ~6 GB | ⚡⚡ Fast (V3) | State of the Art | **Default & Best Overall**: Near large-v3 precision at 8x speed | ⚠️ High-end GPU only |
| **Whisper Large-v3** | Whisper | ~10 GB | ⏱️ Slow | Maximum | Highest precision for critical legal/academic audio | ❌ File Only (Heavy) |
| **Vosk Small** | Vosk / Kaldi | ~300 MB | ⚡⚡⚡ Instant | Decent | **Ultra-lightweight live dictation** on older laptops/CPUs | ✅ **Yes — Ultra Low Resource** |
| **Wav2Vec2** | HuggingFace | ~2 GB | ⚡ Fast | Good | English speech recognition research & benchmarks | ⚠️ GPU Recommended |
| **Qwen3-ASR** | Qwen | ~4 GB | ⚡ Fast | State of the Art | Multilingual code-switching (Tagalog/Filipino, East Asian) | ❌ File Only |

### 💡 Recommendation Cheatsheet

- 🎙️ **Live Meetings & Microphone Capture**: Use **Whisper Base** or **Tiny** (instant streaming without stutter). If on an older PC or laptop, use **Vosk**.
- 🎬 **YouTube Videos, Movies & Subtitles**: Use **Whisper Turbo** (best combination of speed and flawless punctuation/timestamps).
- 🇵🇭 **Tagalog / Taglish / Multilingual Speech**: Use **Whisper Turbo** with language set to **Tagalog** or **Auto-detect**.
- 💻 **Older PC or No Dedicated GPU**: Use **Whisper Tiny** or **Vosk** on CPU mode.
- ⚖️ **Legal, Medical & Academic Precision**: Use **Whisper Large-v3** (run on a dedicated GPU).

---

## 📂 Supported Formats

| Category | Supported Formats |
| :--- | :--- |
| **Audio Files** | `.mp3`, `.wav`, `.m4a`, `.flac`, `.aac`, `.ogg`, `.opus`, `.wma` |
| **Video Files** | `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.wmv`, `.flv` |
| **Export Formats** | Plain Text (`.txt`), SubRip Subtitles (`.srt`), WebVTT (`.vtt`), Timestamps & Segments (`.json`) |

---

## ✨ Features at a Glance

- **100% Offline & Private**: Zero cloud telemetry, zero remote network calls during transcription.
- **Full Drag & Drop**: Drag media directly from your desktop or file manager into JanesCriber.
- **Hardware Acceleration**: Automatic GPU acceleration (NVIDIA CUDA, AMD ROCm, Apple Silicon MPS, Intel XPU, Windows DirectML) with seamless CPU fallback.
- **Live Hardware Telemetry**: Live CPU, RAM, GPU utilization, and processing pipeline monitor.
- **Transcript Library**: Manage, search, read, and export past transcriptions with one click.
- **Custom Cyber-Glass Themes**: Switch between Dark and White Pink / Light themes with customizable accent colors.
- **Keyboard Shortcuts**: `Ctrl+O` to open file, `Ctrl+Enter` to transcribe, `Esc` to close popups.

---

## 🛠️ For Developers & Power Users

If you want to run from source or build hardware-tuned accelerator runtimes:

### Windows Setup
```powershell
git clone https://github.com/jeongchaeul/JanesCriber.git
cd JanesCriber
.\setup.bat
```

### Linux & macOS Setup
```bash
git clone https://github.com/jeongchaeul/JanesCriber.git
cd JanesCriber
chmod +x setup.sh
./setup.sh
```

### Building Release Packages
```powershell
# Windows Consumer Installer & Portable Zip (Zero Terminal Standard)
.\packaging\build_consumer.ps1
```

```bash
# Linux Standalone Tarball
./packaging/build_linux.sh

# macOS Native DMG & Tarball (Apple Silicon & Intel)
./packaging/build_macos.sh
```

---

## 📄 Privacy & Licensing

- **Your Media is Yours**: All audio and video processing is conducted strictly on local hardware.
- **License**: MIT License. See [LICENSE](LICENSE) for details.
- **Dependencies**: FFmpeg is licensed under LGPL/GPL. Pre-trained models (Whisper, Vosk, Qwen) retain their respective open-source licenses.
