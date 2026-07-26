"""The definitions of the helpers the surface names — cited by the ENGINE.

MEASURED, across the four tasks of the fix loop. In three of four, the agent's
very next call after `megabrain_code` was `megabrain_ask`, and all three asks
were the same request: show me the BODY of a helper the surface told me to
call — `content_type` and `attachment` on one task, `resolve_path` on another.
"CITE EVERY HELPER YOU TELL THEM TO REUSE" was a prompt clause, and a clause
is a request the model can ignore — and did, three times out of four.

This is that clause as a mechanism: every backticked name in the prose that
resolves to ONE definition in the index gets that definition cited here, after
the model has answered, with nothing to forget.
"""

from __future__ import annotations

import re

from ..storage import Store
from ._quote import CITATION

__all__ = ["named_definitions", "MAX_NAMED"]

MAX_NAMED = 6
"""Helper definitions cited beyond what the answer already shows.

Six, because four was MEASURED to cut the one that mattered: the send_data
spec named five helpers and the cap dropped `body` — the single helper whose
subtlety (its setter deletes content-length) caused the original second
question. The definitions are short; the cap only guards against a
name-dropping answer pasting half the codebase."""

NAMED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*[!?]?)[^`\n]*`")
"""The leading identifier of a backticked span — `body`, `body(value)`,
`content_type(:json)` all name `content_type`'s kind of thing.

The trailing `[!?]` is Ruby, and its absence was MEASURED. Asked when sinatra's
before filters run, the answer said `dispatch!` was "not shown in the provided
chunks, though its behavior is implied" — and this pass could not rescue it,
because the name was cut at the bang and `dispatch` matches nothing. The index
had `dispatch!` at base.rb:1195 all along. Sinatra's whole request lifecycle is
bang methods (`dispatch!`, `route!`, `filter!`, `invoke`), so on that repository
the omission hit exactly the symbols a walkthrough needs most."""

_CONTAINERS = {"class", "module"}
"""A class's definition is the whole file. Citing it answers nothing."""

_HEADING = re.compile(r"^(h\d+|section)$")
"""A markdown heading is a symbol too, and MEASURED as noise: `ToolError`
matched a `## ToolError` in `tools.md` and pasted 24 lines of user-facing prose
under a heading promising a definition — the one thing the agent said it did
not read. Matched on the kind rather than the file extension because the
extension list belongs to the indexer, and a second copy of it here would
drift."""


def named_definitions(store: Store, surface: str) -> str:
    """Citations for the definition of every helper the prose names."""
    cited = [(path.strip(), int(lo), int(hi))
             for path, lo, hi in CITATION.findall(surface)]
    found: list[str] = []
    for name in dict.fromkeys(NAMED.findall(surface)):
        span = _definition_of(store, name, cited)
        if span and span not in found:
            found.append(span)
        if len(found) == MAX_NAMED:
            break
    if not found:
        return ""
    return ("\n\n## The helpers named above — their definitions, verbatim\n"
            + "\n".join(f"[[{path}:{lo}-{hi}]]" for path, lo, hi in found))


def _definition_of(store: Store, name: str,
                   cited: list[tuple[str, int, int]]) -> tuple[str, int, int] | None:
    """Where `name` is defined — only when that is ONE place.

    Ambiguity resolves toward the files the surface already cites (the
    change's own neighbourhood is the jump the reader means); still ambiguous
    means skipped — a citation that could be the wrong definition looks just
    as authoritative as the right one. Same rule the navigator applies.

    A definition the reader already has in front of them — its span overlaps
    a citation — is skipped: that would be the same range twice.
    """
    defs = [d for d in store.symbols.find(name)
            if d.get("kind") not in _CONTAINERS
            and not _HEADING.match(str(d.get("kind") or ""))
            and isinstance(d.get("line"), int) and isinstance(d.get("end_line"), int)]
    cited_files = {path for path, _, _ in cited}
    picked = [d for d in defs if d["file"] in cited_files] or defs
    if len({(d["file"], d["line"]) for d in picked}) != 1:
        return None
    hit = picked[0]
    file, lo, hi = str(hit["file"]), int(hit["line"]), int(hit["end_line"])
    if any(path == file and start <= hi and lo <= end
           for path, start, end in cited):
        return None
    return file, lo, hi
