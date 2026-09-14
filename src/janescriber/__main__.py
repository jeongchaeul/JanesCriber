"""CLI entry point for JanesCriber."""

from __future__ import annotations

import argparse
import multiprocessing
import sys
from pathlib import Path

from janescriber.pipeline import transcribe_media
from janescriber.paths import project_dir, runtime_paths
from janescriber.pipeline_config import SUPPORTED_ENGINES, validate_transcription_request
from janescriber.runtime import configure_runtime
from janescriber.single_instance import acquire_gui_instance


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transcribe audio and video locally with Whisper or Vosk / Kaldi.")
    parser.add_argument("media", nargs="?", help="Audio or video file to transcribe")
    parser.add_argument("--engine", default="whisper", choices=SUPPORTED_ENGINES, help="Local ASR backend: whisper or vosk")
    parser.add_argument("--model", default="turbo", help="Model name for the selected engine")
    parser.add_argument("--language", default=None, help="Language code, or omit for auto-detection")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing transcript in the Transcripts folder")
    parser.add_argument("--no-cache", action="store_true", help="Run the selected engine again even when a cached transcript exists")
    parser.add_argument("--gui", action="store_true", help="Open the desktop console")
    return parser


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    args = build_parser().parse_args(argv)
    if args.gui or not args.media:
        if not acquire_gui_instance():
            return 0
        configure_runtime(project_dir())
        from janescriber.gui import JanesCriberApp
        JanesCriberApp().mainloop()
        return 0
    print("=" * 68)
    print("JANESCRIBER  |  LOCAL AI TRANSCRIPTION STUDIO")
    print(f"Input: {Path(args.media).resolve()}")
    try:
        config = validate_transcription_request(
            engine=args.engine,
            model_name=args.model,
            language=args.language,
            overwrite=args.overwrite,
            use_cache=not args.no_cache,
        )
        configure_runtime(project_dir())
        paths = runtime_paths()
        result = transcribe_media(
            args.media,
            engine=config.engine,
            model_name=config.model_name,
            language=config.language_arg,
            paths=paths,
            overwrite=config.overwrite,
            use_cache=config.use_cache,
            progress=lambda _, msg: print(f"[*] {msg}"),
        )
    except Exception as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1
    print(f"[+] Done: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
