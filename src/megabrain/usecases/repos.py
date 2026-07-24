"""Which repositories this machine has indexed.

A list of PATHS and nothing else. Counts are read live from each index when
asked, because a registry that caches them is a second source of truth — and
it is always the one that goes stale, which is how a UI ends up confidently
showing a file count from three weeks ago.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from .._home import megabrain_home
from ..contracts import RepoEntry
from ..storage import Store
from ._root import INDEX_FILE

__all__ = ["remember", "known", "registry_path"]


def registry_path() -> Path:
    return megabrain_home() / "registry.json"


def remember(root: Path) -> None:
    """Record a repository as indexed. Idempotent, order preserved."""
    path = str(Path(root).resolve())
    paths = _read()
    if path not in paths:
        _write([*paths, path])


def known() -> list[RepoEntry]:
    """Every registered repository that STILL has an index, with live counts.

    A path whose index is gone is dropped rather than reported: the registry
    accumulates as people move and delete directories, and a rail full of
    entries that fail when clicked is worse than a shorter honest one. The
    pruned list is written back, so the file heals itself.
    """
    paths = _read()
    alive = [p for p in paths if (Path(p) / INDEX_FILE).exists()]
    if alive != paths:
        _write(alive)
    return [_entry(Path(p)) for p in alive]


def _entry(root: Path) -> RepoEntry:
    with Store(root) as store:
        stats = store.stats()
    return RepoEntry(path=str(root), name=root.name,
                     files=stats["files"], chunks=stats["chunks"])


def _read() -> list[str]:
    """Absent, unreadable or malformed all mean "nothing registered yet".

    Fail open: this file is a convenience, and refusing to start because a
    JSON file on the side is corrupt would make it a dependency.
    """
    try:
        loaded: object = json.loads(registry_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    return [str(entry) for entry in cast("list[object]", loaded)]


def _write(paths: list[str]) -> None:
    target = registry_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Written via a temp file and renamed: a crash mid-write would otherwise
    # leave truncated JSON, and the next read would silently see no repos.
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(paths, indent=2), encoding="utf-8")
    temp.replace(target)
