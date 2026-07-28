"""The anti-micro-chunking floor, checked BEFORE any indexing (cheap).

1-line chunks can win span geometry while embedding as noise — the family of
metric-gaming this floor makes un-installable. A small file whose chunks are
naturally small is not the candidate\'s doing, so the floor only fires when
the candidate is also substantially finer than the built-in on the same file.
"""

from __future__ import annotations

from pathlib import Path

from ..chunkers import nws
from ..indexing.chunking import chunker_for
from ..indexing.strategies import Strategy

__all__ = ["granularity_violation", "MIN_MEDIAN_NWS"]

MIN_MEDIAN_NWS = 100       # degenerate-granularity floor for changed files


def granularity_violation(base: Path, candidate: Strategy,
                          files: list[str]) -> str | None:
    from ..indexing.builtin import builtin_strategy_for

    for relpath in files:
        source = (base / relpath).read_text(encoding="utf-8", errors="replace")
        try:
            ours = _median_nws(candidate, relpath, source)
        except Exception as error:                      # noqa: BLE001
            return f"{relpath}: chunk_file raised {type(error).__name__}: {error}"
        if ours is None or ours >= MIN_MEDIAN_NWS:
            continue
        builtin = builtin_strategy_for("." + relpath.rsplit(".", 1)[-1])
        theirs = _median_nws(builtin, relpath, source) if builtin else None
        if theirs and ours < 0.5 * theirs:
            return (f"{relpath}: median chunk is {ours} non-whitespace chars "
                    f"(< {MIN_MEDIAN_NWS}, and <50% of the built-in\'s {theirs}) "
                    f"— chunks this small embed poorly; group more per chunk")
    return None


def _median_nws(strategy: Strategy, relpath: str, source: str) -> int | None:
    chunks = chunker_for(strategy).chunk_file(relpath, source).chunks
    sizes = sorted(nws(chunk.text) for chunk in chunks)
    return sizes[len(sizes) // 2] if sizes else None
