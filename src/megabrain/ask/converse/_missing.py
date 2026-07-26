"""The bodies an answer said it lacked, resolved from the index.

Paired with `_admits`: that module decides WHETHER the answer confessed, this
one produces what to hand back. The pair exists because the widening runs after
the model writes — quoting the body below prose that already hedged about it
leaves the reader to reconcile the two.

Same resolution `_callees` uses, and the same uniqueness rule: a name is worth
serving only when the index resolves it to exactly one definition. Scoped to the
names in the ADMITTING lines, not the whole answer, because the whole answer
names most of the repository.
"""

from __future__ import annotations

from ...storage import Store
from ..checks.callees import NAMED
from ..citing._quote import lines_of
from ._admits import admitted_gap

__all__ = ["missing_bodies", "FILL", "MAX_FILL_LINES"]

MAX_FILL_LINES = 80
"""Lines served per body. A method is tens of lines; past this the model is
being handed a file it did not ask for."""

FILL = """\
You wrote that some code was not shown to you. It IS in this repository, and \
here it is. Rewrite your ENTIRE answer now, using it: state what this code \
actually does rather than what the flow implies, and drop any hedging the \
missing body forced on you. Same citation rules as before — cite, never retype.

"""
"""Deliberately SHORT, and that is MEASURED rather than a matter of style.

The engine is deterministic at temperature 0 — three runs came back
byte-identical — which made the comparison exact. Adding one more demand to this
text, that the served lines be cited by path, fixed a malformed citation and
BROUGHT BACK the hedge it exists to remove. Asking for more at once bought less
of what mattered, the same lesson `OPENING` cost to learn.

So the citation is not asked for here at all: `_unresolved` in `_quote` deletes a
bracket the grammar never accepted, which is the deterministic half of the same
problem and cannot trade itself against the prose."""


def missing_bodies(store: Store, raw: str) -> str:
    """Verbatim bodies for the symbols named in lines that admit a gap."""
    wanted: dict[str, tuple[str, int, int]] = {}
    for line in raw.split("\n"):
        if not admitted_gap(line):
            continue
        for name in NAMED.findall(line):
            span = _definition(store, name)
            if span:
                wanted.setdefault(name, span)
    return "".join(_quoted(store, name, *span) for name, span in wanted.items())


def _definition(store: Store, name: str) -> tuple[str, int, int] | None:
    """Where `name` is defined, when the index says exactly one place."""
    found = [d for d in store.symbols.find(name)
             if isinstance(d.get("line"), int) and isinstance(d.get("end_line"), int)]
    if len({(d["file"], d["line"]) for d in found}) != 1:
        return None
    hit = found[0]
    return str(hit["file"]), int(hit["line"]), int(hit["end_line"])


def _quoted(store: Store, name: str, path: str, lo: int, hi: int) -> str:
    """The real lines, numbered the way `open_file` numbers them.

    Numbered because that is what the model already knows how to read bounds
    off, and it is what lets the rewrite cite a sub-range accurately.
    """
    lines = lines_of(store, path)
    if not lines:
        return ""
    hi = min(hi, len(lines), lo + MAX_FILL_LINES - 1)
    body = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(lo, hi + 1))
    return f"{path} — `{name}` at L{lo}-{hi}\n{body}\n\n"
