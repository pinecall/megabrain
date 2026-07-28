"""The WALKTHROUGH prompt: what the narrator is asked, over retrieved chunks.

Assembled from four pieces that change for different reasons — `_opening` (go
and look), `_rules` (cite, never write), `_chunkblocks` (what retrieval found)
and the question itself. The blocks are shared with `grep`, because the balance
between quoted bodies and a listed map is measured and must not drift between
two deliverables that both depend on it.
"""

from __future__ import annotations

from ...converse.chunkblocks import chunk_blocks
from ...storage.model import ChunkMeta

__all__ = ["build_prompt", "RULES", "OPENING"]

from ._opening import OPENING
from ._rules import RULES


def build_prompt(question: str, candidates: list[ChunkMeta],
                 context: str = "") -> str:
    """The cite-only walkthrough prompt over numbered chunks.

    `context` is a previous walkthrough of the same area, prose only. It is
    explicitly NON-CITABLE: the model may use it to know what matters and in
    what order, but every line of code still has to come from a numbered chunk.
    """
    return (f"You are a senior engineer giving a complete code walkthrough that "
            f"answers the developer's query. Cover the ENTIRE relevant flow end "
            f"to end — do not stop early, do not leave a thread dangling.\n\n"
            f"{OPENING}\n"
            f"STRICT RULES:\n{RULES}\n\nQUERY: {question}\n"
            f"{_context(context)}\n"
            f"RETRIEVED CHUNKS:\n\n" + chunk_blocks(candidates))


def _context(context: str) -> str:
    """A previous walkthrough, marked NON-CITABLE in the strongest terms.

    Without that line the model cites it, the splicer finds no chunk behind the
    citation, and the block silently disappears from the answer.
    """
    if not context.strip():
        return ""
    return ("\nCONTEXT — a previous walkthrough over the SAME code. Use it to "
            "know what matters and in what order. It is NOT citable: every "
            "line of code must still come from a numbered chunk below.\n\n"
            f"{context}\n")


