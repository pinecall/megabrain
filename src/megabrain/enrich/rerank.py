"""The judge lane: a cheap model orders the RELATED tier.

Retrieval is recall-safe by design, and that has a cost: a file that merely
SHARES VOCABULARY with the query — a test, an eval script, an A/B gate —
survives, because cosine cannot tell "implements scoring" from "tests
scoring". This lane fixes exactly that. The model returns IDS; the engine
keeps and reorders its own verbatim chunks. It selects, it never writes.

Fail-open everywhere, all-or-nothing across batches. No provider, a timeout, a
malformed reply, an unknown id: the deterministic bundle is returned
untouched. The model is an OPTIMISATION, never a dependency.
"""

from __future__ import annotations

from .._models import RERANK_MODEL
from ..contracts import Bundle, Tier2File
from ..providers.chat import ChatProvider
from ._batches import RERANK_TIMEOUT, verdict_of
from ._cards import listing
from ._prompt import PROMPT
from ._verdict import ids_in

__all__ = ["rerank", "judge_provider", "RERANK_MODEL"]

MAX_TOKENS = 300



def judge_provider(model: str | None = None) -> ChatProvider | None:
    """A provider tuned for JUDGING, not for narrating.

    The default and its measurements live in `_models`; a repository overrides
    it in `megabrain.json`. It must NOT inherit the narration model — that one
    is chosen to explain code well and costs seconds per call, and three
    batches through it took 16s for a JSON array of integers.

    Built here rather than inherited: the lane's model and its timeout are the
    lane's business, and sharing the narrator's meant sharing a model chosen to
    explain code — seconds per call, for a task whose whole output is a JSON
    array of integers.
    """
    from ..providers.chat import OpenAICompatible

    provider = OpenAICompatible(model=model or RERANK_MODEL,
                                timeout=RERANK_TIMEOUT)
    return provider if provider.available() else None


def rerank(bundle: Bundle, provider: ChatProvider) -> Bundle:
    """Reorder tier 2 by the judge's verdict. Never drops, never rewrites."""
    related = list(bundle["tier2"])
    if len(related) < 2:
        return bundle
    try:
        order = verdict_of(_judge, provider, bundle["query"], related)
    except Exception:                         # noqa: BLE001 — fail open, always
        return bundle
    # The verdict TRAVELS. An empty order reorders nothing, and returning the
    # bundle byte-identical made "judged and rejected everything" look exactly
    # like "the lane never ran" — discarding the one signal the evidence band
    # cannot compute, since the band reads the top-1 cosine and the top-1 is
    # often right while the rest of the list is noise.
    kept = len(dict.fromkeys(index for index in order if 0 <= index < len(related)))
    return {**bundle, "tier2": _reordered(related, order),
            "judge": {"kept": kept, "of": len(related)}}


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
