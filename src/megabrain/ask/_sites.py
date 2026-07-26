"""The edit sites: the model names symbols, the ENGINE numbers them.

`grep` exists because the host's editor makes you open the file anyway, so
citing the code back is work paid for twice — the reason `megabrain_code` was
retired. What a grep replacement owes is narrower and cheaper: which files,
which symbols inside them, one line on why each matters, and the exact range to
jump to.

The split of labour is the design, and both halves were measured. Asking a model
for line numbers is rejected in `prompt.py`: "unnumbered, `[[k:lo-hi]]` citations
landed a few lines off and cut functions mid-body." Asking it which symbol
matters is what it is good at. So the model writes `send_file` and the index
reads L425-448, where it cannot be off by one.
"""

from __future__ import annotations

import re

from ..storage import Store
from ._mentions import mentioned_sites
from ._referenced import referenced_sites
from ._spans import span_of

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
    """The model's rows plus every site the task's own identifiers appear in.

    Two lanes, and the second is not a nicety. MEASURED head to head against a
    plain grep on the same feature: `grep show_envvar` returned all six sites in
    one call, the model named two, and one of the four it dropped was where the
    logic goes. A tool that replaces grep must return at least what grep returns,
    so completeness is COMPUTED here rather than requested in a prompt — while
    the model still contributes the row grep cannot find and the note saying why.
    """
    grouped: dict[str, list[tuple[int, int, str]]] = {}
    for path, symbol, note in ROW.findall(raw):
        span = span_of(store, path.strip(), symbol.strip())
        if span:
            grouped.setdefault(path.strip(), []).append(
                (*span, f"{symbol.strip()} — {note.strip()[:MAX_NOTE]}"))
    _add_mentions(store, task, grouped)
    return "".join(
        f"## {path}\n" + "\n".join(f"  L{low}-{high}  {label}"
                                   for low, high, label in sorted(rows)) + "\n\n"
        for path, rows in grouped.items())


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
    _place(grouped, referenced_sites(store, settled), "used by a site above")


def _place(grouped: dict[str, list[tuple[int, int, str]]],
           sites: list[tuple[str, str, int, int]], why: str) -> None:
    """Add each site once, keyed by its span so the model's note always wins."""
    for path, symbol, low, high in sites:
        rows = grouped.setdefault(path, [])
        if not any(low == known_low and high == known_high
                   for known_low, known_high, _ in rows):
            rows.append((low, high, f"{symbol} — {why}"))
