"""Scans a source's incoming directory for files matching its configured
glob pattern, so the pipeline knows what's available to (re)ingest.
"""

from __future__ import annotations

from pathlib import Path


def scan_incoming(incoming_dir: str | Path, file_pattern: str | None = None) -> list[Path]:
    """Returns files in incoming_dir matching file_pattern (default: all
    files), sorted by name. Hidden files (dotfiles like .gitkeep) are
    skipped. Missing directories yield an empty list rather than raising."""
    directory = Path(incoming_dir)
    if not directory.exists():
        return []
    pattern = file_pattern or "*"
    return sorted(
        p for p in directory.glob(pattern)
        if p.is_file() and not p.name.startswith(".")
    )
