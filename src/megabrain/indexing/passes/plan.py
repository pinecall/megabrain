"""Phase 1 — decide what to chunk, and chunk it. Pure CPU, no network.

Everything here happens before a single byte goes to the embedding endpoint,
which is what lets phase 2 send one request instead of one per file.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable

from ...chunkers import Chunker, FileResult, validate_partition
from ...storage import Store
from ..discover import Discovery
from ..strategies import Registry

__all__ = ["Planned", "Plan", "plan"]

Progress = Callable[[dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class Planned:
    relpath: str
    sha: str
    result: FileResult


def _no_planned() -> list[Planned]:
    return []


def _no_paths() -> list[str]:
    return []


@dataclass(slots=True)
class Plan:
    """What one pass decided to do, before anything was done.

    The factories are named rather than `list`, which reads as an untyped
    container to a strict checker and loses the element type everywhere the
    field is used.
    """

    pending: list[Planned] = field(default_factory=_no_planned)
    unchanged: list[str] = field(default_factory=_no_paths)
    violations: int = 0


def plan(discovery: Discovery, store: Store, registry: Registry, *,
         force: bool, sources: dict[str, str],
         on_progress: Progress | None = None) -> Plan:
    """Chunk every file whose content changed; note the rest as unchanged.

    Incrementality is by content hash, not mtime: a checkout, a rebase or a
    formatter run all touch timestamps without changing what the file says, and
    re-embedding on that would make routine git operations cost money.
    """
    out = Plan()
    for index, found in enumerate(discovery.files, start=1):
        strategy = registry.for_path(found.relpath)
        if strategy is None:
            continue
        source = sources[found.relpath]
        sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        changed = force or store.files.sha(found.relpath) != sha
        if changed:
            result = Chunker(strategy.parse).chunk_file(found.relpath, source)
            out.violations += bool(validate_partition(result))
            out.pending.append(Planned(found.relpath, sha, result))
        else:
            out.unchanged.append(found.relpath)
        _tick(on_progress, index, len(discovery.files), found.relpath, changed)
    return out


def _tick(on_progress: Progress | None, index: int, total: int,
          relpath: str, changed: bool) -> None:
    if on_progress is not None:
        on_progress({"type": "file", "file": relpath, "i": index,
                     "n": total, "changed": changed})


def read_sources(discovery: Discovery) -> dict[str, str]:
    """Every file's text, read once and reused by chunking and edge extraction.

    `errors="replace"` rather than skipping: a file with one bad byte is still
    mostly code, and dropping it would remove it from the index entirely for a
    problem that affects a single character.
    """
    return {found.relpath: found.path.read_text(encoding="utf-8", errors="replace")
            for found in discovery.files}
