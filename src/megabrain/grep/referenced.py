"""What the edit SITES reference — the last file a literal search cannot reach.

MEASURED: adding `show_envvar_value` to click needs a key on the
`OptionHelpExtra` TypedDict in ANOTHER file, and no literal search finds it —
its body never contains `show_envvar`. But the site that must change is
declared `-> types.OptionHelpExtra`, the index HAS that link, and one hop out
from each site (resolved by the navigator's uniqueness rule) reaches the file
neither grep nor the model named. ONE hop, deliberately: following what the
referenced file references in turn walks the repository.
"""

from __future__ import annotations

import re

from ..storage import Store
from ..storage.lines import lines_of
from .idents import identifiers

__all__ = ["referenced_sites", "MAX_REFERENCED"]

MAX_REFERENCED = 6
"""Rows this hop may add — what a densely-typed function can still contribute
after the two filters below drop nearly everything its body names."""

MAX_REF_SPAN = 40
"""Lines a referenced symbol may span to count as a target worth listing.
MEASURED: `Option.__init__`'s 80-line body named six helpers, ate the cap, and
`OptionHelpExtra` never got in. What survives is SMALL — the shape of a
contract (a TypedDict, a Protocol) or of a helper worth jumping to."""

_HEADING = re.compile(r"^(h\d+|section)$")


def referenced_sites(store: Store, sites: list[tuple[str, str, int, int]],
                     ) -> list[tuple[str, str, int, int]]:
    """Symbols the bodies of `sites` name, when the index resolves them to one.

    A same-file reference counts when it falls OUTSIDE every shown span — the
    reader is pointed at a LINE RANGE, not a file. On rails the behaviour
    behind `assert_enqueued_with` lived 300 lines below in the same module and
    the old rule ("already there") cost three calls."""
    known = {(path, low, high) for path, _, low, high in sites}
    per_site: list[list[tuple[str, str, int, int]]] = []
    for path, _, low, high in sites:
        body = _body(store, path, low, high)
        rows: list[tuple[str, str, int, int]] = []
        # READING order, not set order: the body's own order is the ranking
        # the reader would build — what the site touches first, first.
        for name in sorted(identifiers(body), key=body.find):
            row = _resolved(store, name)
            if row is None or _shown(row, known):
                continue
            if (row[0], row[2], row[3]) not in known and row not in rows:
                rows.append(row)
        per_site.append(rows)
    return _fairly(per_site)


def _fairly(per_site: list[list[tuple[str, str, int, int]]]
            ) -> list[tuple[str, str, int, int]]:
    """One reference per site per round, up to the cap.

    First-come spent the whole cap on whichever sites the map listed FIRST —
    on rails the lane found `prepare_args_for_assertion` over its own site and
    the full map never showed it. The cap bounds the render; fairness decides
    who it starves, and it must never be the site the task is about."""
    found: list[tuple[str, str, int, int]] = []
    for round_index in range(MAX_REFERENCED):
        for rows in per_site:
            if round_index < len(rows) and rows[round_index] not in found:
                found.append(rows[round_index])
                if len(found) == MAX_REFERENCED:
                    return found
    return found


def _shown(row: tuple[str, str, int, int],
           known: set[tuple[str, int, int]]) -> bool:
    """Already inside a span the map gives for that file — not a second place
    to go. What survives of the old same-file rule: its true half."""
    path, _, low, high = row
    return any(a <= low and high <= b for p, a, b in known if p == path)


def _body(store: Store, path: str, low: int, high: int) -> str:
    lines = lines_of(store, path)
    return "\n".join(lines[low - 1:high])


def _resolved(store: Store, name: str) -> tuple[str, str, int, int] | None:
    """Where `name` is declared, when that is exactly one jumpable place."""
    found = [entry for entry in store.symbols.find(name)
             if entry["end_line"] - entry["line"] < MAX_REF_SPAN
             and not _HEADING.match(str(entry.get("kind") or ""))]
    if len({(entry["file"], entry["line"]) for entry in found}) != 1:
        return None
    hit = found[0]
    return str(hit["file"]), name, int(hit["line"]), int(hit["end_line"])
