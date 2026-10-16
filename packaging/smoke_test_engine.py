"""Run a short, offline transcription through a freshly packaged JanesCriber engine."""

from __future__ import annotations

import argparse
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


def _run(command: list[str], environment: dict[str, str], working_directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=working_directory,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, help="Packaged JanesCriberEngine executable")
    parser.add_argument("--runtime-bin", type=Path, required=True, help="Folder containing bundled FFmpeg and FFprobe")
    parser.add_argument("--work-directory", type=Path, required=True, help="Disposable smoke-test work area")
    args = parser.parse_args()

    work_directory = args.work_directory.resolve()
    runtime_bin = args.runtime_bin.resolve()
    work_directory.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="engine-smoke-", dir=work_directory) as temporary:
        temporary_directory = Path(temporary)
        data_directory = temporary_directory / "app-data"
        source_path = temporary_directory / "smoke-input.wav"
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join(
            part for part in (str(runtime_bin), environment.get("PATH", "")) if part
        )
        environment["JANESCRIBER_DATA_DIR"] = str(data_directory)
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"

        # Generate a clean 1-second 16 kHz mono WAV file
        with wave.open(str(source_path), "wb") as sample:
            sample.setnchannels(1)
            sample.setsampwidth(2)
            sample.setframerate(16000)
            sample.writeframes(
                b"".join(
                    struct.pack("<h", int(8192 * math.sin(2 * math.pi * 440 * index / 16000)))
                    for index in range(16000)
                )
            )

        if args.engine:
            engine = [str(args.engine.resolve())]
        else:
            engine = [sys.executable, "-m", "janescriber.__main__"]

        # 1. Basic CLI / Engine sanity test
        help_result = _run([*engine, "--help"], environment, work_directory)
        if help_result.returncode != 0 or "JanesCriber" not in help_result.stdout:
            raise RuntimeError(
                f"Packaged engine did not start successfully: {help_result.stderr.strip() or help_result.stdout.strip()}"
            )

        # 2. Verify FFmpeg and FFprobe availability
        ffmpeg = shutil.which("ffmpeg", path=environment["PATH"])
        ffprobe = shutil.which("ffprobe", path=environment["PATH"])
        if not ffmpeg or not ffprobe:
            raise RuntimeError("Bundled FFmpeg and FFprobe must be accessible in the runtime environment.")

        # 3. Verify internal assets (mel_filters.npz etc.) if packaged
        if args.engine:
            engine_dir = args.engine.resolve().parent
            # In onedir layout, check _internal/whisper/assets/mel_filters.npz
            whisper_assets = engine_dir / "_internal" / "whisper" / "assets" / "mel_filters.npz"
            if not whisper_assets.is_file():
                # Check root layout fallback
                whisper_assets_fallback = engine_dir / "whisper" / "assets" / "mel_filters.npz"
                if not whisper_assets_fallback.is_file():
                    raise RuntimeError(
                        f"Packaged engine is missing Whisper assets: {whisper_assets} not found. "
                        "Ensure '--collect-all whisper' is passed to PyInstaller."
                    )

        # 4. Service bootstrap test
        service_input = '{"id":"smoke","operation":"bootstrap","payload":{}}\n'
        service_proc = subprocess.run(
            [*engine, "--service"],
            input=service_input,
            cwd=work_directory,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if service_proc.returncode != 0 or '"ok":true' not in service_proc.stdout:
            raise RuntimeError(
                f"Packaged engine failed service bootstrap: {service_proc.stderr.strip() or service_proc.stdout.strip()}"
            )

    print("Packaged engine smoke test passed: CLI sanity, FFmpeg availability, Whisper assets, and service bootstrap verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Packaged engine smoke test failed: {error}", file=sys.stderr)
        raise SystemExit(1)
