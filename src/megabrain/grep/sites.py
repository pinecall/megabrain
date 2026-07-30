"""The edit sites: which symbols, their real ranges, and what is in scope.

`grep` exists because the host's editor opens the file anyway, so citing the code
back is work paid for twice — the reason `megabrain_code` was retired. What a
grep replacement owes is narrower: which files, which symbols, the exact range to
jump to, and the metadata that saves a Read (`_surface`).

Four lanes feed it, three of them with NO model: identifiers from the task
(`_mentions`), one hop to the contracts those sites reference (`_referenced`),
the import surface (`_surface`), and — only when asked — a model's rows and notes.
Every range comes from the index, because asking a model for line numbers is
rejected in `prompt.py`: unnumbered, its citations "landed a few lines off".
"""

from __future__ import annotations

import re

from ..storage import Store
from .mentions import mentioned_sites
from .referenced import referenced_sites
from .rows import rendered
from .spans import span_of

__all__ = ["sites_from", "MAX_NOTE", "ROW"]

MAX_NOTE = 100
"""Characters of explanation per symbol.

The reader is about to open the file; this line only has to say why THIS symbol
and not its neighbour. Unbounded, it grows back into the walkthrough `ask`
already gives you."""

ROW = re.compile(r"^\s*([^|\n]+?\.[A-Za-z0-9]+)\s*\|\s*([^|\n]+?)\s*\|\s*([^\n]*)$",
                 re.MULTILINE)
"""`path | symbol | note`, one per line.

The `\\.[A-Za-z0-9]+` on the path is what separates a data row from prose that
happens to contain a pipe: a path carries a file extension and a sentence does
not. Models preface and summarise no matter what they are told, so the parse
takes rows and ignores everything else rather than failing on the first
paragraph."""


def sites_from(store: Store, raw: str, *, task: str = "") -> str:
    """The model's rows plus every site the task's identifiers appear in.

    MEASURED head to head: `grep show_envvar` returned all six sites in one call
    while the model named two, and one it dropped was where the logic goes. A tool
    replacing grep must return at least what grep returns, so completeness is
    COMPUTED rather than requested — the model contributes only the row grep
    cannot find, and the note saying why."""
    grouped: dict[str, list[tuple[int, int, str]]] = {}
    for path, symbol, note in ROW.findall(raw):
        span = span_of(store, path.strip(), symbol.strip())
        if span:
            grouped.setdefault(path.strip(), []).append(
                (*span, f"{symbol.strip()} — {note.strip()[:MAX_NOTE]}"))
    _add_mentions(store, task, grouped)
    return "".join(rendered(store, path, rows) for path, rows in grouped.items())


def _add_mentions(store: Store, task: str,
                  grouped: dict[str, list[tuple[int, int, str]]]) -> None:
    """Sites the task's identifiers name that the model did not, marked as such.

    Marked rather than merged silently: the reader can tell which rows carry a
    model's judgement about why they matter and which are "this text is here",
    and the second kind is what a grep would have given them anyway.
    """
    if not task:
        return
    sites = [(path, symbol, low, high)
             for path, symbol, low, high in mentioned_sites(store, task)]
    _place(grouped, sites, "mentions it")
    # One hop out from what we have, which is the only lane that reaches a file
    # the task's own words never name: `Option.get_help_extra` is declared
    # `-> types.OptionHelpExtra`, and that TypedDict had to gain a key.
    settled = sites + [(path, "", low, high)
                       for path, rows in grouped.items() for low, high, _ in rows]
    for row, uses in referenced_sites(store, settled):
        # The score travels in the note: "used by 3 sites above" is the rank a
        # reader can act on, and one more word than the row already carried.
        note = "used by a site above" if uses == 1 else f"used by {uses} sites above"
        _place(grouped, [row], note)


def _place(grouped: dict[str, list[tuple[int, int, str]]],
           sites: list[tuple[str, str, int, int]], why: str) -> None:
    """Add each site once, keyed by its span so the model's note always wins."""
    for path, symbol, low, high in sites:
        rows = grouped.setdefault(path, [])
        if not any(low == known_low and high == known_high
                   for known_low, known_high, _ in rows):
            rows.append((low, high, f"{symbol} — {why}"))
