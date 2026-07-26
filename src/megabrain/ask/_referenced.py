"""What the edit SITES reference — the last file a literal search cannot reach.

MEASURED, and it is the row that survived two rounds of fixing. Adding
`show_envvar_value` to click needs a key added to the `OptionHelpExtra` TypedDict
in ANOTHER file, and no literal search finds it: its body never contains the
string `show_envvar`. The plain-grep arm needed a separate search and paid four
calls groping for it.

But the site that must change, `Option.get_help_extra`, is declared
`-> types.OptionHelpExtra`. The index HAS that link. So one hop out from each
site — resolved by the same uniqueness rule the navigator applies to a jump —
reaches the file neither grep nor the model named.

ONE hop, deliberately. Following what the referenced file references in turn
walks the repository, and this render exists to avoid exactly that.
"""

from __future__ import annotations

import re

from ..storage import Store
from ._idents import identifiers
from ._quote import lines_of

__all__ = ["referenced_sites", "MAX_REFERENCED"]

MAX_REFERENCED = 6
"""Rows this hop may add.

A site's body names many things; the two filters below drop nearly all of them,
and this caps what a densely-typed function can still contribute."""

MAX_REF_SPAN = 40
"""Lines a referenced symbol may span to count as a CONTRACT worth extending.

Both filters here were MEASURED on the first working version, which added six
rows and still missed the one that mattered: `Option.__init__`'s 80-line body
named `_pick_type`, `_validate`, `_resolve_lazy_default` and three more, ate the
cap, and `OptionHelpExtra` never got in.

What survives is cross-file AND small, which is what a contract looks like — a
TypedDict, a dataclass, a Protocol. `OptionHelpExtra` is 5 lines in another file
and had to gain a key; `ParamType` is 174 lines in another file and is only used.
A same-file helper is dropped outright: the reader is already in that file."""

_HEADING = re.compile(r"^(h\d+|section)$")


def referenced_sites(store: Store, sites: list[tuple[str, str, int, int]],
                     ) -> list[tuple[str, str, int, int]]:
    """Symbols the bodies of `sites` name, when the index resolves them to one."""
    known = {(path, low, high) for path, _, low, high in sites}
    found: list[tuple[str, str, int, int]] = []
    for path, _, low, high in sites:
        for name in identifiers(_body(store, path, low, high)):
            row = _resolved(store, name)
            if row is None or row[0] == path:
                continue          # same file: the reader is already there
            if (row[0], row[2], row[3]) not in known and row not in found:
                found.append(row)
    return found[:MAX_REFERENCED]


def _body(store: Store, path: str, low: int, high: int) -> str:
    lines = lines_of(store, path)
    return "\n".join(lines[low - 1:high])


def _resolved(store: Store, name: str) -> tuple[str, str, int, int] | None:
    """Where `name` is declared, when that is exactly one jumpable place."""
    found = [entry for entry in store.symbols.find(name)
             if isinstance(entry.get("line"), int)
             and isinstance(entry.get("end_line"), int)
             and int(entry["end_line"]) - int(entry["line"]) < MAX_REF_SPAN
             and not _HEADING.match(str(entry.get("kind") or ""))]
    if len({(entry["file"], entry["line"]) for entry in found}) != 1:
        return None
    hit = found[0]
    return str(hit["file"]), name, int(hit["line"]), int(hit["end_line"])
