"""Which files a candidate actually re-chunks — the gate\'s whole scope.

Exactly the files whose retrieval could move, so exactly what must be
measured: a shape-router touches a family of files, not just the one target
someone had in mind.
"""

from __future__ import annotations

from pathlib import Path

from ..indexing.chunking import chunker_for
from ..indexing.strategies import Strategy

__all__ = ["changed_files"]

_SKIP = {".git", "node_modules", "__pycache__", ".megabrain", "dist", "build"}


def changed_files(root: Path, candidate: Strategy,
                  baseline: Strategy | None = None) -> list[str]:
    """Files whose chunk spans differ between candidate and reference."""
    from ..indexing.builtin import builtin_strategy_for

    base = Path(root).resolve()
    out: list[str] = []
    for ext in candidate.exts:
        reference = baseline or builtin_strategy_for(ext)
        if reference is None:
            continue
        for path in sorted(base.rglob(f"*{ext}")):
            relpath = path.relative_to(base).as_posix()
            if not path.is_file() or set(relpath.split("/")) & _SKIP:
                continue
            if _spans_differ(candidate, reference, relpath, path):
                out.append(relpath)
    return out


def _spans_differ(candidate: Strategy, reference: Strategy,
                  relpath: str, path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        ours = chunker_for(candidate).chunk_file(relpath, source)
        theirs = chunker_for(reference).chunk_file(relpath, source)
    except Exception:                                   # noqa: BLE001
        return False
    return ([(c.start_line, c.end_line) for c in ours.chunks]
            != [(c.start_line, c.end_line) for c in theirs.chunks])
