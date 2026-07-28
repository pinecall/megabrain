"""The uncovered-extension census. Deterministic, no model.

What forge would forge FOR: every text extension in the repository that the
active registry — built-ins plus already-trusted repo strategies — cannot
index, with counts and sample paths. Nothing here decides to generate
anything; it only names the gap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, TypedDict

from ..indexing._exclude import Excluder, load_ignore
from ..indexing.builtin import default_registry
from ..indexing.discover import MAX_FILE_BYTES
from ..indexing.trust import load_repo_strategies

__all__ = ["detect", "Candidate", "MIN_FILES", "SKIP_EXTS"]

MIN_FILES = 2
"""Below this, no forge: writing a chunker for one stray file costs more than
the file could ever answer."""

# Never worth chunking: binary or noise even when the suffix survives a text read.
SKIP_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".pdf", ".zip",
    ".gz", ".tar", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4",
    ".sqlite", ".db", ".lock", ".map", ".min.js", ".pyc", ".class", ".jar",
    ".wasm", ".svg",
})


class Candidate(TypedDict):
    ext: str
    files: int
    bytes: int
    paths: list[str]
    samples: list[str]


def detect(root: Path | str, exclude: Sequence[str] = ()) -> list[Candidate]:
    """Uncovered extensions, biggest population first, each with three samples
    spread by size — the smallest, the median and the largest, because a
    chunker written from three same-shaped files fails on the fourth shape."""
    base = Path(root).resolve()
    covered = set(default_registry(load_repo_strategies(base)).extensions)
    excluder = Excluder.build([*load_ignore(base), *exclude])
    found: dict[str, list[Path]] = {}
    for path in sorted(base.rglob("*")):
        ext = path.suffix.lower()
        if not path.is_file() or not ext or ext in covered or ext in SKIP_EXTS:
            continue
        if excluder.excludes(path.relative_to(base).as_posix()):
            continue
        if _unreadable(path):
            continue
        found.setdefault(ext, []).append(path)
    return [_candidate(base, ext, files)
            for ext, files in sorted(found.items(), key=lambda kv: -len(kv[1]))
            if len(files) >= MIN_FILES]


def _candidate(base: Path, ext: str, files: list[Path]) -> Candidate:
    by_size = sorted(files, key=lambda p: p.stat().st_size)
    samples = list(dict.fromkeys(
        [by_size[0], by_size[len(by_size) // 2], by_size[-1]]))
    return Candidate(
        ext=ext, files=len(files),
        bytes=sum(p.stat().st_size for p in files),
        paths=[p.relative_to(base).as_posix() for p in files],
        samples=[p.relative_to(base).as_posix() for p in samples])


def _unreadable(path: Path) -> bool:
    """Too big, or binary — a NUL in the head is the cheap, reliable sniff."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return True
        return b"\0" in path.read_bytes()[:2048]
    except OSError:
        return True
