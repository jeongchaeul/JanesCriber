#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FFMPEG_PATH=""
FFPROBE_PATH=""
OUTPUT_DIR="$REPO_ROOT/dist"
KEEP_STAGING=0
BUILD_ROOT=""

usage() {
  cat <<'EOF'
Usage: packaging/build_macos.sh [options]
  --ffmpeg PATH       native FFmpeg executable
  --ffprobe PATH      native FFprobe executable
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

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS release packages must be built natively on Darwin." >&2
  exit 1
fi

ARCH="$(uname -m)"
if [[ "$ARCH" != "arm64" && "$ARCH" != "x86_64" ]]; then
  echo "Unsupported architecture: $ARCH. macOS releases support arm64 and x86_64." >&2
  exit 1
fi
if [[ "$(sysctl -in sysctl.proc_translated 2>/dev/null || true)" == "1" ]]; then
  echo "Rosetta-translated builds are not supported; run the build natively." >&2
  exit 1
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required build tool not found: $1" >&2
    exit 1
  }
}

resolve_executable() {
  local explicit="$1" command_name="$2" description="$3" resolved directory
  if [[ -n "$explicit" ]]; then
    directory="$(cd -- "$(dirname -- "$explicit")" && pwd)"
    resolved="$directory/$(basename -- "$explicit")"
  else
    resolved="$(command -v "$command_name" || true)"
  fi
  if [[ -z "$resolved" || ! -f "$resolved" || ! -x "$resolved" ]]; then
    echo "$description was not found or is not executable. Pass its explicit path." >&2
    exit 1
  fi
  printf '%s\n' "$resolved"
}

assert_macho_arch() {
  local executable="$1" description="$2" architectures
  if ! file "$executable" | grep -q 'Mach-O'; then
    echo "$description is not a Mach-O executable: $executable" >&2
    exit 1
  fi
  architectures="$(lipo -archs "$executable")"
  if ! grep -qw "$ARCH" <<<"$architectures"; then
    echo "$description does not contain the native $ARCH architecture: $architectures" >&2
    exit 1
  fi
}

cleanup() {
  if ((KEEP_STAGING == 0)) && [[ -n "$BUILD_ROOT" && -d "$BUILD_ROOT" && "$BUILD_ROOT" == "$OUTPUT_DIR"/consumer-build-* ]]; then
    rm -rf -- "$BUILD_ROOT"
  fi
}
trap cleanup EXIT

for command_name in uv npm cargo codesign file find grep hdiutil install lipo shasum sysctl xattr; do
  require_command "$command_name"
done

FFMPEG_PATH="$(resolve_executable "$FFMPEG_PATH" ffmpeg FFmpeg)"
FFPROBE_PATH="$(resolve_executable "$FFPROBE_PATH" ffprobe FFprobe)"
assert_macho_arch "$FFMPEG_PATH" FFmpeg
assert_macho_arch "$FFPROBE_PATH" FFprobe
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
BUILD_ROOT="$OUTPUT_DIR/consumer-build-$VERSION-macos-$ARCH"
PAYLOAD_ROOT="$BUILD_ROOT/payload"
APP_BUNDLE="$PAYLOAD_ROOT/JanesCriber.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
RUNTIME_ROOT="$APP_RESOURCES/runtime"
RUNTIME_ENGINE="$RUNTIME_ROOT/engine"
RUNTIME_BIN="$RUNTIME_ROOT/bin"
PYINSTALLER_ROOT="$BUILD_ROOT/pyinstaller"
TAURI_TARGET="$BUILD_ROOT/tauri-target"
DMG_OUTPUT="$OUTPUT_DIR/JanesCriber-$VERSION-macos-$ARCH.dmg"
TAR_OUTPUT="$OUTPUT_DIR/JanesCriber-$VERSION-macos-$ARCH.tar.gz"

rm -rf -- "$BUILD_ROOT"
rm -f -- "$DMG_OUTPUT" "$DMG_OUTPUT.sha256" "$TAR_OUTPUT" "$TAR_OUTPUT.sha256"
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

mkdir -p -- "$APP_MACOS" "$APP_RESOURCES"
TAURI_EXECUTABLE="$TAURI_TARGET/release/janescriber-studio"
if [[ ! -x "$TAURI_EXECUTABLE" ]]; then
  TAURI_EXECUTABLE="$TAURI_TARGET/release/janescriber"
fi
[[ -x "$TAURI_EXECUTABLE" ]] || {
  echo "Tauri did not produce the expected executable." >&2
  exit 1
}
install -m 0755 -- "$TAURI_EXECUTABLE" "$APP_MACOS/JanesCriber"

cat > "$APP_CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>JanesCriber</string>
  <key>CFBundleIdentifier</key>
  <string>com.projectaspyr.janescriber.studio</string>
  <key>CFBundleName</key>
  <string>JanesCriber</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$VERSION</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.15</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

codesign --force --deep --sign - "$APP_BUNDLE"

hdiutil create -volname "JanesCriber" -srcfolder "$PAYLOAD_ROOT" -ov -format UDZO "$DMG_OUTPUT"
(
  cd -- "$OUTPUT_DIR"
  shasum -a 256 "$(basename -- "$DMG_OUTPUT")" >"$(basename -- "$DMG_OUTPUT").sha256"
)

tar -C "$PAYLOAD_ROOT" -czf "$TAR_OUTPUT" JanesCriber.app
(
  cd -- "$OUTPUT_DIR"
  shasum -a 256 "$(basename -- "$TAR_OUTPUT")" >"$(basename -- "$TAR_OUTPUT").sha256"
)

echo "Created $DMG_OUTPUT and $TAR_OUTPUT"
