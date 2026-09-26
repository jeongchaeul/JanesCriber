#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FFMPEG_PATH=""
FFPROBE_PATH=""
OUTPUT_DIR="$REPO_ROOT/dist"
KEEP_STAGING=0

usage() {
  cat <<'EOF'
Usage: packaging/build_linux.sh [options]
  --ffmpeg PATH       static-compatible FFmpeg executable
  --ffprobe PATH      static-compatible FFprobe executable
  --output-dir PATH   artifact directory (default: dist)
  --keep-staging      retain the intermediate payload
EOF
}

while (($#)); do
  case "$1" in
    --ffmpeg) FFMPEG_PATH="${2:?missing value for --ffmpeg}"; shift 2 ;;
    --ffprobe) FFPROBE_PATH="${2:?missing value for --ffprobe}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:?missing value for --output-dir}"; shift 2 ;;
    --keep-staging) KEEP_STAGING=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" && "$ARCH" != "amd64" ]]; then
  echo "Unsupported architecture: $ARCH. Linux releases are x86_64 only." >&2
  exit 1
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required build tool not found: $1" >&2
    exit 1
  }
}

resolve_executable() {
  local explicit="$1" command_name="$2" description="$3" resolved
  if [[ -n "$explicit" ]]; then
    resolved="$(realpath -- "$explicit")"
  else
    resolved="$(command -v "$command_name" || true)"
  fi
  if [[ -z "$resolved" || ! -f "$resolved" || ! -x "$resolved" ]]; then
    echo "$description was not found or is not executable. Pass its explicit path." >&2
    exit 1
  fi
  printf '%s\n' "$resolved"
}

for command_name in uv npm cargo tar sha256sum install realpath; do
  require_command "$command_name"
done

FFMPEG_PATH="$(resolve_executable "$FFMPEG_PATH" ffmpeg FFmpeg)"
FFPROBE_PATH="$(resolve_executable "$FFPROBE_PATH" ffprobe FFprobe)"
"$FFMPEG_PATH" -version >/dev/null
"$FFPROBE_PATH" -version >/dev/null
cargo --version >/dev/null

cd -- "$REPO_ROOT"
uv sync --locked --python 3.11
uv run --locked pyinstaller --version >/dev/null
VERSION="$(uv run --locked python -c 'import re; print(re.search(r"__version__\s*=\s*\"([^\"]+)\"", open("src/janescriber/__init__.py").read()).group(1))' 2>/dev/null)"
if [[ -z "$VERSION" ]]; then
  echo "Could not determine the version from src/janescriber/__init__.py." >&2
  exit 1
fi

OUTPUT_DIR="$(mkdir -p -- "$OUTPUT_DIR" && cd -- "$OUTPUT_DIR" && pwd)"
BUILD_ROOT="$OUTPUT_DIR/consumer-build-$VERSION-linux-x86_64"
PAYLOAD_ROOT="$BUILD_ROOT/payload/JanesCriber"
RUNTIME_ROOT="$PAYLOAD_ROOT/resources/runtime"
RUNTIME_ENGINE="$RUNTIME_ROOT/engine"
RUNTIME_BIN="$RUNTIME_ROOT/bin"
PYINSTALLER_ROOT="$BUILD_ROOT/pyinstaller"
TAURI_TARGET="$BUILD_ROOT/tauri-target"
ARCHIVE="$OUTPUT_DIR/JanesCriber-$VERSION-linux-x86_64.tar.gz"

rm -rf -- "$BUILD_ROOT"
rm -f -- "$ARCHIVE" "$ARCHIVE.sha256"
mkdir -p -- "$RUNTIME_ENGINE" "$RUNTIME_BIN" "$PYINSTALLER_ROOT/spec"

echo "Building the frozen engine (onedir)..."
uv run --locked pyinstaller --noconfirm --clean --onedir --contents-directory _internal \
  --name JanesCriberEngine \
  --paths "$REPO_ROOT/src" \
  --hidden-import vosk \
  --collect-all vosk \
  --hidden-import transformers \
  --collect-submodules transformers.models.wav2vec2 \
  --distpath "$PYINSTALLER_ROOT/dist" \
  --workpath "$PYINSTALLER_ROOT/work" \
  --specpath "$PYINSTALLER_ROOT/spec" \
  "$REPO_ROOT/packaging/engine_entry.py"

BUILT_ENGINE="$PYINSTALLER_ROOT/dist/JanesCriberEngine"
[[ -x "$BUILT_ENGINE/JanesCriberEngine" ]] || {
  echo "PyInstaller did not produce the expected onedir engine." >&2
  exit 1
}
cp -a -- "$BUILT_ENGINE/." "$RUNTIME_ENGINE/"
install -m 0755 -- "$FFMPEG_PATH" "$RUNTIME_BIN/ffmpeg"
install -m 0755 -- "$FFPROBE_PATH" "$RUNTIME_BIN/ffprobe"
if [[ -f "$REPO_ROOT/LICENSE" ]]; then
  install -m 0644 -- "$REPO_ROOT/LICENSE" "$PAYLOAD_ROOT/LICENSE"
fi
install -m 0644 -- "$REPO_ROOT/README.md" "$PAYLOAD_ROOT/README.md"
"$RUNTIME_ENGINE/JanesCriberEngine" --help >/dev/null

if find "$RUNTIME_ROOT" -type f \( \
  -name 'gui.py' -o -name 'customtkinter' -o \
  -name 'Program.cs' -o -name 'pip' -o -name 'npm' -o \
  -name 'cargo' -o -name 'rustc' \) -print -quit | grep -q .; then
  echo "Private runtime contains a forbidden source or build-tool file." >&2
  exit 1
fi
if find "$PAYLOAD_ROOT" -maxdepth 1 -type f -name '*.py' -print -quit | grep -q .; then
  echo "Payload root contains unexpected loose Python source files." >&2
  exit 1
fi

TAURI_CONFIG="$BUILD_ROOT/tauri.release.json"
export JANESCRIBER_RELEASE_VERSION="$VERSION"
export JANESCRIBER_TAURI_CONFIG="$TAURI_CONFIG"
uv run --locked python - <<'PY'
import json
import os
from pathlib import Path

source = Path("desktop-ui/src-tauri/tauri.conf.json")
config = json.loads(source.read_text(encoding="utf-8"))
config["productName"] = "JanesCriber"
config["version"] = os.environ["JANESCRIBER_RELEASE_VERSION"]
config["build"]["beforeBuildCommand"] = ""
config["bundle"]["active"] = False
config["bundle"]["targets"] = []
Path(os.environ["JANESCRIBER_TAURI_CONFIG"]).write_text(
    json.dumps(config, indent=2) + "\n", encoding="utf-8"
)
PY

echo "Building the production Tauri UI..."
export CARGO_TARGET_DIR="$TAURI_TARGET"
export npm_config_cache="$BUILD_ROOT/npm-cache"
(
  cd -- "$REPO_ROOT/desktop-ui"
  npm ci --no-audit --no-fund --ignore-scripts
  npm run build
  ./node_modules/.bin/tauri build --no-bundle --config "$TAURI_CONFIG"
)

TAURI_EXECUTABLE="$TAURI_TARGET/release/janescriber-studio"
if [[ ! -x "$TAURI_EXECUTABLE" ]]; then
  TAURI_EXECUTABLE="$TAURI_TARGET/release/janescriber"
fi
[[ -x "$TAURI_EXECUTABLE" ]] || {
  echo "Tauri did not produce the expected executable." >&2
  exit 1
}
install -m 0755 -- "$TAURI_EXECUTABLE" "$PAYLOAD_ROOT/JanesCriber"

tar -C "$BUILD_ROOT/payload" -czf "$ARCHIVE" JanesCriber
(
  cd -- "$OUTPUT_DIR"
  sha256sum "$(basename -- "$ARCHIVE")" >"$(basename -- "$ARCHIVE").sha256"
)
echo "Created $ARCHIVE"

if ((KEEP_STAGING == 0)); then
  rm -rf -- "$BUILD_ROOT"
fi
