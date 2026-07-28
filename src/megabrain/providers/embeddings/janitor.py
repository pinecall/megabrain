"""Measuring and sweeping the embedding cache — explicitly, never by itself.

The cache is content-addressed and sound, and it never shrank: every model
ever pointed at kept its full corpus of vectors forever, so switching models
twice on a large repository tripled the footprint silently. The sweep is
mtime-based and lives behind `megabrain cache prune` — deleting cache while an
index runs is how you pay for the same vectors twice, so nothing here is ever
called automatically.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

__all__ = ["measured", "swept"]


def measured(root: Path) -> tuple[int, int]:
    """(entries, bytes) currently on disk. Zero for a cache that never wrote."""
    entries = size = 0
    for path in _vectors(root):
        try:
            size += path.stat().st_size
            entries += 1
        except OSError:
            continue                   # unlinked underneath us — not our entry
    return entries, size


def swept(root: Path, older_than_days: float) -> tuple[int, int]:
    """Remove entries untouched for `older_than_days`; (removed, bytes freed).

    mtime, not atime: reads through `EmbedCache.get` do not touch the file, so
    "old" means "not re-written lately" — a corpus still being indexed rewrites
    nothing and re-reads everything, which is why this is never automatic.
    """
    cutoff = time.time() - older_than_days * 86400.0
    removed = freed = 0
    for path in _vectors(root):
        try:
            stat = path.stat()
            if stat.st_mtime < cutoff:
                path.unlink()
                removed += 1
                freed += stat.st_size
        except OSError:
            continue                   # a raced entry is somebody else's hit
    return removed, freed


def _vectors(root: Path) -> "list[Path]":
    if not root.is_dir():
        return []
    return [Path(dirpath) / name
            for dirpath, _, names in os.walk(root)
            for name in names if not name.endswith(".tmp")]
