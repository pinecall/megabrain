"""What the edit SITES reference — the last file a literal search cannot reach.

MEASURED: adding `show_envvar_value` to click needs a key on a TypedDict in
ANOTHER file whose body never contains `show_envvar` — but the site that must
change is declared `-> types.OptionHelpExtra`, the index HAS that link, and
one hop out (resolved by the navigator's uniqueness rule) reaches the file
neither grep nor the model named. ONE hop, deliberately: following what the
referenced file references in turn walks the repository.
"""

from __future__ import annotations

import re

from ..storage import Store
from ..storage.lines import lines_of
from .idents import identifiers

__all__ = ["referenced_sites", "MAX_REFERENCED"]

MAX_REFERENCED = 15
"""Rows this hop may add. Was 6, and six starved real maps (rails#52478: the
task's own helper competed for the last slot). The filters below plus the
score in `_ranked` keep fifteen from becoming noise — every row is unique,
small, and outside every shown span."""

MAX_REF_SPAN = 40
"""Lines a referenced symbol may span to count as a target worth listing.
MEASURED: `Option.__init__`'s 80-line body named six helpers, ate the cap, and
the TypedDict that mattered never got in. What survives is SMALL — the shape
of a contract or of a helper worth jumping to."""

_HEADING = re.compile(r"^(h\d+|section)$")

Reference = tuple[str, str, int, int]


def referenced_sites(store: Store, sites: list[Reference],
                     ) -> list[tuple[Reference, int]]:
    """Symbols the bodies of `sites` name, with their USE COUNT across sites.

    A same-file reference counts when it falls OUTSIDE every shown span: the
    reader is pointed at a LINE RANGE, not a file — on rails the behaviour
    lived 300 lines below in the same module and re-finding it cost 3 calls."""
    known = {(path, low, high) for path, _, low, high in sites}
    per_site: list[list[Reference]] = []
    for path, _, low, high in sites:
        body = _body(store, path, low, high)
        rows: list[Reference] = []
        # READING order, not set order: the body's own order is the ranking
        # the reader would build — what the site touches first, first.
        for name in sorted(identifiers(body), key=body.find):
            row = _resolved(store, name)
            if row is None or _shown(row, known):
                continue
            if (row[0], row[2], row[3]) not in known and row not in rows:
                rows.append(row)
        per_site.append(rows)
    return _ranked(per_site)


def _ranked(per_site: list[list[Reference]]) -> list[tuple[Reference, int]]:
    """Scored by how many distinct SITES reference it, round-robin as the tie.

    A symbol two edit sites depend on is the task's shared contract; one a
    single site touches is that site's detail (SITES, not mentions). The tie
    is one-per-site-per-round fairness, so the cap never starves the task's
    own site — measured on rails, where first-come spent every slot first."""
    uses: dict[Reference, int] = {}
    position: dict[Reference, tuple[int, int]] = {}
    for site_index, rows in enumerate(per_site):
        for round_index, row in enumerate(rows):
            uses[row] = uses.get(row, 0) + 1
            position.setdefault(row, (round_index, site_index))
    ranked = sorted(uses, key=lambda row: (-uses[row], position[row]))
    return [(row, uses[row]) for row in ranked[:MAX_REFERENCED]]


def _shown(row: tuple[str, str, int, int],
           known: set[tuple[str, int, int]]) -> bool:
    """Inside a span the map already gives for that file — not a second place
    to go; the old same-file rule's true half."""
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
