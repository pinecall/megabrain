"""Turning each arm's output into comparable `(path, line, line)` rows.

`resolve` goes through the engine's own `span_of` rather than a second lookup: the
benchmark must grade against the ranges megabrain would really hand a reader, and
a private copy of that resolution would let the two drift until the benchmark
measured itself.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from megabrain.ask.sites.spans import span_of
from megabrain.storage import Store

__all__ = ["mb_rows", "grep_hits", "resolve"]

_ROW = re.compile(r"^  L(\d+)-(\d+)")

# Extensions the cases live in. grep is given the same corpus megabrain indexed,
# so neither arm is credited or blamed for a file the other never saw.
_INCLUDE = ("*.py", "*.js", "*.rb")
_PRUNE = ("node_modules", ".git", ".megabrain")


def mb_rows(render: str) -> list[tuple[str, int, int]]:
    """`## path` headers plus their `L<low>-<high>` rows."""
    out: list[tuple[str, int, int]] = []
    current = ""
    for line in render.split("\n"):
        if line.startswith("## "):
            current = line[3:].strip()
        elif found := _ROW.match(line):
            out.append((current, int(found.group(1)), int(found.group(2))))
    return out


def grep_hits(root: Path, pattern: str) -> tuple[list[tuple[str, int]], str]:
    """`grep -rn` as an agent runs it: hits, and the raw output it has to read."""
    done = subprocess.run(
        ["grep", "-rn", *[f"--include={glob}" for glob in _INCLUDE],
         *[f"--exclude-dir={name}" for name in _PRUNE], pattern, "."],
        cwd=root, capture_output=True, text=True, check=False)
    hits: list[tuple[str, int]] = []
    for line in done.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) >= 2 and parts[1].isdigit():
            hits.append((parts[0].removeprefix("./"), int(parts[1])))
    return hits, done.stdout


def resolve(root: Path, relpath: str, symbol: str) -> tuple[int, int] | None:
    """A ground-truth symbol as the line range the index holds for it.

    None when the index has no such symbol, which `measure.py` reports as a
    stale expectation instead of silently scoring it as a miss — an upstream
    rename must look like a broken benchmark, not like a regression.
    """
    with Store(root) as store:
        return span_of(store, relpath, symbol)
