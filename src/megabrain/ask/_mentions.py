"""Every symbol that literally mentions an identifier the TASK named.

MEASURED head to head, and this is the lane that lost it. Asked to add
`show_envvar_value` beside the existing `show_envvar`, a plain `grep show_envvar`
returned all six sites in one call; the model named two, and one it dropped was
where the logic goes (`get_help_extra`). Reordered slightly, that miss ships a
flag that never fires.

A tool that replaces grep must return at least what grep returns, so
completeness is COMPUTED rather than asked for: identifiers from the task,
matched literally, resolved to the symbols containing them. The model still
contributes what grep cannot — the site whose text mentions nothing.
"""

from __future__ import annotations

import re

from ..storage import Store
from ._idents import identifiers, outermost
from ._spans import MAX_SPAN

__all__ = ["mentioned_sites", "MAX_SPREAD"]

MAX_SPREAD = 40
"""Symbols an identifier may resolve to before it is treated as vocabulary.

A name in forty places is the repository's idiom, not this task's target, and
listing all of them would bury the rows the reader needs."""

_HEADING = re.compile(r"^(h\d+|section)$")
"""A markdown heading is a symbol too, and a useless edit site: `CHANGES.md`
declares one per release, each spanning to the end of the file."""


def mentioned_sites(store: Store, task: str) -> list[tuple[str, str, int, int]]:
    """`(path, symbol, low, high)` for every symbol whose body names one.

    The identifiers come from the task itself, so this is the literal search a
    caller would have run by hand — with the match resolved to the symbol that
    contains it, which is the part a grep cannot do.
    """
    wanted = identifiers(task)
    if not wanted:
        return []
    hits: list[tuple[str, str, int, int]] = []
    for path, symbols in _by_file(store, wanted).items():
        hits.extend((path, name, low, high) for name, low, high in outermost(symbols))
    return hits if len(hits) <= MAX_SPREAD else []


def _by_file(store: Store, wanted: set[str]) -> dict[str, list[tuple[str, int, int]]]:
    """Symbols containing any wanted identifier, grouped by file.

    Read from the chunk TEXT rather than a symbol name match: the identifier is
    being USED at these sites, not declared, which is exactly why a name lookup
    finds the declaration and misses the five places that touch it.
    """
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, wanted))) + r")\b")
    found: dict[str, list[tuple[str, int, int]]] = {}
    for meta in store.chunks.read_metas():
        if not pattern.search(meta.text or ""):
            continue
        lines = (meta.text or "").split("\n")
        touched = {meta.start_line + offset
                   for offset, line in enumerate(lines) if pattern.search(line)}
        for entry in store.symbols.read_for(meta.file):
            row = _site(entry, touched)
            if row and row not in found.setdefault(meta.file, []):
                found[meta.file].append(row)
    return found


def _site(entry: dict[str, object], touched: set[int]) -> tuple[str, int, int] | None:
    """One symbol as a jumpable row, if it contains a match and is worth a jump.

    The size rule is the same one the model's own rows get, and here it is what
    makes the lane usable at all: markdown headings are symbols whose span runs
    to the end of the document, so a task naming any identifier matched 29
    `CHANGES.md` "Version x.y.z" sections at L1-1630 each — 48 sites, past the
    spread cap, and the lane returned nothing while holding the row that mattered.
    """
    low, high = entry.get("line"), entry.get("end_line")
    if not (isinstance(low, int) and isinstance(high, int)):
        return None
    if high - low >= MAX_SPAN or _HEADING.match(str(entry.get("kind") or "")):
        return None
    if not any(low <= line <= high for line in touched):
        return None
    return str(entry.get("name")), low, high
