"""The machine-checkable gate between generated code and the index.

A candidate strategy is accepted only if it chunks EVERY matching file in the
repository cleanly: the module loads, a class claims the extension, `parse`
never raises, the resulting chunks are an exact line partition, and every
symbol's span lies inside its file. Failures come back as a report precise
enough to drive the repair loop — the model fixes what the oracle names.
"""

from __future__ import annotations

from pathlib import Path

from ..chunkers import FileResult, validate_partition
from ..indexing.chunking import chunker_for
from ..indexing.trust import instantiate_strategies

__all__ = ["validate_strategy", "MAX_REPORTED"]

MAX_REPORTED = 20      # errors per report: enough to repair, not a flood


def validate_strategy(root: Path | str, code: str, ext: str,
                      paths: list[str]) -> tuple[bool, str, dict[str, int]]:
    """(ok, report, stats) over every matching file — the oracle."""
    base = Path(root).resolve()
    try:
        strategies = instantiate_strategies(code, origin=f"<candidate {ext}>")
    except Exception as error:                          # noqa: BLE001
        return False, f"module failed to load: {type(error).__name__}: {error}", {}
    strategy = next((s for s in strategies if ext in s.exts), None)
    if strategy is None:
        return False, f'no strategy class claiming exts=("{ext}",) was found', {}

    errors: list[str] = []
    stats = {"files": 0, "chunks": 0, "symbols": 0}
    chunker = chunker_for(strategy, repo=base.name)
    for relpath in paths:
        source = (base / relpath).read_text(encoding="utf-8", errors="replace")
        try:
            result = chunker.chunk_file(relpath, source)
        except Exception as error:                      # noqa: BLE001
            errors.append(f"{relpath}: parse raised {type(error).__name__}: {error}")
            continue
        errors.extend(f"{relpath}: partition violation: {violation}"
                      for violation in validate_partition(result))
        errors.extend(_symbol_errors(relpath, result))
        stats["files"] += 1
        stats["chunks"] += len(result.chunks)
        stats["symbols"] += len(result.symbols)
    if errors:
        return False, "\n".join(errors[:MAX_REPORTED]), stats
    return True, (f"{stats['files']} files -> {stats['chunks']} chunks, "
                  f"{stats['symbols']} symbols, partition clean"), stats


def _symbol_errors(relpath: str, result: FileResult) -> list[str]:
    """A symbol pointing outside its file poisons every jump built on it."""
    return [f"{relpath}: symbol {symbol.name!r} spans L{symbol.line}-"
            f"{symbol.end_line} but the file has {result.total_lines} lines"
            for symbol in result.symbols
            if not 1 <= symbol.line <= symbol.end_line
            or symbol.end_line > result.total_lines]
