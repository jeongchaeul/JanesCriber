# Rebuilding JanesCriber Executables

This guide documents the exact, reliable procedure for rebuilding both the Python transcription engine (`JanesCriberEngine.exe`) and the Tauri desktop application (`janescriber-studio.exe`).

> [!CRITICAL]
> **NEVER invoke bare `cargo build --release` to produce the desktop executable!**
> Bare `cargo build` bypasses the Tauri build macro, leaving the app in development fallback mode pointing to `devUrl` (`http://127.0.0.1:1421`). When launched without a running Vite dev server, the desktop window will display a connection error.
>
> You **MUST** use `npm run tauri:build -- --no-bundle` inside `desktop-ui/` so production web assets are compiled and embedded directly into the standalone binary.

---

## Prerequisites & Environment

- **Python & uv:** Python 3.11 managed via `uv` (`uv sync --locked`).
- **Node.js:** Node.js 22 and `npm`. On Windows, ensure Node.js is on PATH (`$env:PATH = "D:\node.js\Node.js;" + $env:PATH`).
- **Rust toolchain:** Latest stable toolchain with Cargo.

---

## Step 1: Rebuilding the Frozen Engine (`JanesCriberEngine.exe`)

Run from the repository root:

```powershell
uv run --locked pyinstaller --noconfirm --clean --onedir --contents-directory _internal `
    --name JanesCriberEngine `
    --paths "src" `
    --hidden-import proctap `
    --hidden-import proctap.backends.windows `
    --hidden-import vosk `
    --collect-all vosk `
    --collect-all whisper `
    --hidden-import transformers `
    --collect-submodules transformers.models.wav2vec2 `
    --distpath "build_engine\dist" `
    --workpath "build_engine\work" `
    --specpath "build_engine\spec" `
    "packaging\engine_entry.py"
```

### Verification & Smoke Test
```powershell
python packaging\smoke_test_engine.py `
    --engine "build_engine\dist\JanesCriberEngine\JanesCriberEngine.exe" `
    --runtime-bin "D:\Programs\JanesCriber\runtime\bin" `
    --work-directory "temp\smoke"
```
Expected output: `Packaged engine smoke test passed: CLI sanity, FFmpeg availability, Whisper assets, and service bootstrap verified.`

---

## Step 2: Rebuilding the Desktop Application (`janescriber-studio.exe`)

Run from the `desktop-ui` directory:

```powershell
cd desktop-ui
$env:PATH = "D:\node.js\Node.js;" + $env:PATH
npm run tauri:build -- --no-bundle
```

This compiles web assets into `desktop-ui/dist`, then compiles Rust with assets embedded directly into:
`desktop-ui/src-tauri/target/release/janescriber-studio.exe`

---

## Step 3: Deploying Binaries to Local Installation (`D:\Programs\JanesCriber\`)

1. **Stop any existing instances first** (Windows locks open executables):
   ```powershell
   Stop-Process -Name "*janescriber*" -Force -ErrorAction SilentlyContinue
   ```

2. **Deploy the desktop executable:**
   ```powershell
   Copy-Item -Path "desktop-ui\src-tauri\target\release\janescriber-studio.exe" `
             -Destination "D:\Programs\JanesCriber\janescriber-studio.exe" -Force
   ```

3. **Deploy the engine:**
   ```powershell
   Copy-Item -Path "build_engine\dist\JanesCriberEngine\*" `
             -Destination "D:\Programs\JanesCriber\runtime\engine" -Recurse -Force
   ```

4. **Clean up staging files:**
   ```powershell
   Remove-Item -Path "build_engine" -Recurse -Force -ErrorAction SilentlyContinue
   ```

---

## Step 4: Full Release Installer / Packaging (Optional)

To build the full Windows installer and portable release bundle:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_consumer.ps1
```
