"""The candidate card the judge reads.

One header per chunk plus its verbatim body. The header carries the id it must
answer with, and the body is what it weighs — measured better than a window,
because partial evidence invites a confident WRONG exclusion.
"""

from __future__ import annotations

from ..contracts import Tier2File

__all__ = ["listing"]

MAX_BODY = 2400


def listing(batch: list[Tier2File], offset: int) -> str:
    return "\n".join(_card(entry, offset + position)
                     for position, entry in enumerate(batch))


def _card(entry: Tier2File, identifier: int) -> str:
    best = entry["best_chunk"]
    if best is None:
        return f'[{identifier}] {entry["file"]} · (no span)'
    head = (f'[{identifier}] {entry["file"]}:L{best["start_line"]}-{best["end_line"]}'
            f' · {best["name"] or "?"} ({best["kind"]})')
    # Truncated per card rather than by dropping cards: a candidate the judge
    # never sees cannot be ranked, and an id missing from every batch is
    # indistinguishable from one the judge rejected.
    return f'{head}\n{(best["text"] or "")[:MAX_BODY]}'
