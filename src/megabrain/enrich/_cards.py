"""The candidate card the judge reads.

WHAT THE JUDGE SEES was measured, not assumed — 6 ground-truth queries × 4
views × 3 repetitions:

    view                          target kept   median rank
    1 query-aware line               18/18           2
    6-line window                    12/18           —
    full bodies, ONE call            15/18           1
    full bodies, batches of 8        18/18           1

Full bodies win, in small batches. And partial evidence is WORSE than little
evidence: on the cross-subsystem query — where the answering file never
mentions the state the question asks about — every mid-size view dropped the
answer, while the one-line view and the batched full-body view kept it. A
six-line window shows the judge just enough to be confidently wrong.

So: one header per chunk, carrying the id it must answer with, plus the
verbatim body.
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
