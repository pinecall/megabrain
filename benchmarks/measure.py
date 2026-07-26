"""Run the benchmark: coverage, tokens and wall-clock, as a markdown table.

    python benchmarks/measure.py [--repos DIR]

Both arms are charged for the WHOLE job — find the sites, then read them — because
discovery is the cheap half and what decides the bill is what you open afterwards.

A megabrain row carries the symbol's exact range, so the read is that range. A
grep hit is one line with no boundaries: to see where a function ends you read
around it, so the arm is charged a window (`WINDOW` either side, merged). That is
GENEROUS to grep — the honest worst case is the whole file, reported as a third
row, and it is what an agent does when the hit sits in a 3 600-line module.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from cases import CASES, Case
from rows import grep_hits, mb_rows, resolve
from spans import file_lines, read_cost, tokens

from megabrain.usecases.grep import grep

WINDOW = 60
"""Lines either side of a grep hit, counted as what a reader would open.

Sixty is enough to see a small function whole and is charged in grep's favour: it
is less than the file, and the arm gets the benefit of a reader who guesses the
window right first time."""


def main(repos: Path) -> int:
    print("| repo | via | discover | read | **total** | ms |")
    print("|---|---|---:|---:|---:|---:|")
    for case in CASES:
        root = repos / case.dirname
        if not (root / ".megabrain").exists():
            print(f"| {case.name} | NOT INDEXED — run benchmarks/setup.sh | | | | |")
            continue
        _row(case, root)
    print()
    _coverage(repos)
    return 0


def _row(case: Case, root: Path) -> None:
    started = time.perf_counter()
    render = grep(root, case.task)
    mb_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    hits, raw = grep_hits(root, case.grep)
    grep_ms = (time.perf_counter() - started) * 1000

    windows = [(path, max(1, line - WINDOW), line + WINDOW) for path, line in hits]
    whole = [(path, 1, len(file_lines(root, path))) for path in {p for p, _ in hits}]
    for label, discover, read, elapsed in (
            ("**megabrain**", tokens(render), read_cost(root, mb_rows(render)), mb_ms),
            ("grep + window", tokens(raw), read_cost(root, windows), grep_ms),
            ("grep + whole file", tokens(raw), read_cost(root, whole), grep_ms)):
        name = case.name if label.startswith("**") else ""
        print(f"| {name} | {label} | {discover} | {read} | **{discover + read}** "
              f"| {elapsed:.0f} |")


def _coverage(repos: Path) -> None:
    """Which arm returned each site the change actually needs."""
    print("| repo | site the change needs | megabrain | grep |")
    print("|---|---|:-:|:-:|")
    for case in CASES:
        root = repos / case.dirname
        if not (root / ".megabrain").exists():
            continue
        rows = mb_rows(grep(root, case.task))
        hits, _ = grep_hits(root, case.grep)
        for relpath, symbol, why in case.sites:
            span = resolve(root, relpath, symbol)
            if span is None:
                print(f"| {case.name} | `{symbol}` NOT IN INDEX — stale pin? | — | — |")
                continue
            low, high = span
            # Overlap, not containment: a row is a hit on this site if it lands
            # anywhere inside the symbol — which is what a reader needs.
            in_mb = any(path == relpath and not (top < low or bottom > high)
                        for path, bottom, top in rows)
            in_grep = any(path == relpath and low <= line <= high
                          for path, line in hits)
            print(f"| {case.name} | `{symbol}` — {why} "
                  f"| {'yes' if in_mb else '**no**'} "
                  f"| {'yes' if in_grep else '**no**'} |")


if __name__ == "__main__":
    argv = sys.argv[1:]
    default = Path(__file__).resolve().parent / "repos"
    where = Path(argv[argv.index("--repos") + 1]) if "--repos" in argv else default
    try:
        raise SystemExit(main(where))
    except FileNotFoundError as exc:
        print(f"missing: {exc}. Run benchmarks/setup.sh first.", file=sys.stderr)
        raise SystemExit(1) from exc
