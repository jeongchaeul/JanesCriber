"""Safe discovery and reading of JanesCriber transcript outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_TRANSCRIPT_SUFFIXES = frozenset({".txt", ".srt", ".vtt", ".json"})


@dataclass(frozen=True)
class TranscriptEntry:
    path: Path
    size: int
    modified: float


def discover_transcripts(program_dir: str | Path) -> list[TranscriptEntry]:
    """Return direct managed-folder transcripts, newest first."""
    base = Path(program_dir).resolve()
    entries: list[TranscriptEntry] = []
    try:
        for path in base.iterdir():
            if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_TRANSCRIPT_SUFFIXES:
                continue
            try:
                stat = path.stat()
                entries.append(TranscriptEntry(path, stat.st_size, stat.st_mtime))
            except OSError:
                continue
    except OSError:
        return []
    return sorted(entries, key=lambda entry: entry.modified, reverse=True)


def is_managed_transcript(path: str | Path, program_dir: str | Path) -> bool:
    """Allow library actions only for .txt files directly in the app folder."""
    candidate = Path(path).resolve()
    base = Path(program_dir).resolve()
    return candidate.is_file() and candidate.suffix.lower() in SUPPORTED_TRANSCRIPT_SUFFIXES and candidate.parent == base


def read_transcript(path: str | Path, program_dir: str | Path) -> str:
    candidate = Path(path).resolve()
    if not is_managed_transcript(candidate, program_dir):
        raise ValueError("This file is not a JanesCriber library transcript.")
    return candidate.read_text(encoding="utf-8", errors="replace")
