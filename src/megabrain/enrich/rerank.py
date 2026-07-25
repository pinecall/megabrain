"""The judge lane: a cheap model orders the RELATED tier.

Retrieval is recall-safe by design, and that has a cost: a file that merely
SHARES VOCABULARY with the query — a test, an eval script, an A/B gate —
survives, because cosine cannot tell "implements scoring" from "tests
scoring". This lane fixes exactly that. The model returns IDS; the engine
keeps and reorders its own verbatim chunks. It selects, it never writes.

WHAT THE JUDGE SEES was measured rather than assumed (6 ground-truth queries
× 4 views × 3 repetitions):

    view                          target kept   median rank
    1 query-aware line               18/18           2
    6-line window                    12/18           —
    full bodies, ONE call            15/18           1
    full bodies, batches of 8        18/18           1

Partial evidence is worse than little evidence: on the cross-subsystem query
every mid-size view dropped the answer, while the one-line and the batched
views kept it. Small pools per call stop the judge ruling files out
confidently — the price is a looser keep, and completeness beats ordering.

Fail-open everywhere, all-or-nothing across batches. No provider, a timeout, a
malformed reply, an unknown id: the deterministic bundle is returned
untouched. The model is an OPTIMISATION, never a dependency.
"""

from __future__ import annotations

from ..contracts import Bundle, Tier2File
from ..providers.chat import ChatProvider
from ._cards import listing
from ._prompt import PROMPT
from ._verdict import ids_in, round_robin

__all__ = ["rerank", "RERANK_BATCH"]

# Measured: one 29-candidate call missed 3 of 18 targets that batches of 8 all
# kept. The batch size is the finding, not a tuning knob.
RERANK_BATCH = 8
MAX_TOKENS = 300

def rerank(bundle: Bundle, provider: ChatProvider) -> Bundle:
    """Reorder tier 2 by the judge's verdict. Never drops, never rewrites."""
    related = list(bundle["tier2"])
    if len(related) < 2:
        return bundle
    try:
        order = _verdict(provider, bundle["query"], related)
    except Exception:                         # noqa: BLE001 — fail open, always
        return bundle
    return {**bundle, "tier2": _reordered(related, order)}


def _verdict(provider: ChatProvider, question: str,
             related: list[Tier2File]) -> list[int]:
    """Every batch judged, merged round-robin. Raises to fail the whole lane.

    All-or-nothing: a partial verdict is a ranking derived from half the
    evidence, which is worse than the deterministic order it would replace.
    """
    batches = [related[start:start + RERANK_BATCH]
               for start in range(0, len(related), RERANK_BATCH)]
    offsets = range(0, len(related), RERANK_BATCH)
    ranked = [_judge(provider, question, batch, start)
              for batch, start in zip(batches, offsets)]
    return round_robin(ranked)


def _judge(provider: ChatProvider, question: str, batch: list[Tier2File],
           offset: int) -> list[int]:
    reply = provider.chat_text(
        getattr(provider, "model", ""),
        PROMPT.format(question=question, listing=listing(batch, offset)),
        max_tokens=MAX_TOKENS)
    picked = ids_in(reply)
    valid = range(offset, offset + len(batch))
    return [identifier for identifier in picked if identifier in valid]


def _reordered(related: list[Tier2File], order: list[int]) -> list[Tier2File]:
    """Picked first, in the judge's order; everything else keeps its place
    behind them.

    Unpicked entries are MOVED, never deleted. The recall floors exist so a
    bundle can only gain files — a judge that removed one would undo that from
    above, and the reader would never learn what was taken.
    """
    picked = [related[index] for index in order if 0 <= index < len(related)]
    seen = {id(entry) for entry in picked}
    return [*picked, *(entry for entry in related if id(entry) not in seen)]
