"""Judging the candidates in small PARALLEL batches.

Two findings, both measured, and they pull in opposite directions:

* the batch must be SMALL — one 29-candidate call missed 3 of 18 targets that
  batches of 8 all kept, because a big pool lets the judge rule files out
  confidently;
* which means several calls, so they must run AT THE SAME TIME. Serially the
  lane cost three round trips end to end (16s through a narration model); the
  batches are independent by construction, so it should cost the slowest one.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Protocol

from ..providers.chat import ChatProvider
from ._verdict import round_robin

if TYPE_CHECKING:
    from ..contracts import Tier2File

__all__ = ["verdict_of", "RERANK_BATCH", "RERANK_TIMEOUT"]

RERANK_BATCH = 8
RERANK_TIMEOUT = 30.0


class Judge(Protocol):
    def __call__(self, provider: ChatProvider, question: str,
                 batch: "list[Tier2File]", offset: int) -> list[int]: ...


def verdict_of(judge: Judge, provider: ChatProvider, question: str,
               related: "list[Tier2File]") -> list[int]:
    """Every batch judged, merged round-robin. Raises to fail the whole lane.

    All-or-nothing: a partial verdict is a ranking derived from half the
    evidence, which is worse than the deterministic order it would replace.
    """
    offsets = list(range(0, len(related), RERANK_BATCH))
    batches = [related[start:start + RERANK_BATCH] for start in offsets]
    # PARALLEL. Serially this was three round trips added end to end — the
    # batches are independent by construction, so the lane should cost the
    # slowest one, not their sum. Measured: 16s serial through the narration
    # model, and the whole point of the lane is that it costs almost nothing.
    pool = ThreadPoolExecutor(max_workers=len(batches))
    try:
        running = [pool.submit(judge, provider, question, batch, start)
                   for batch, start in zip(batches, offsets)]
        # `result(timeout)` on each, so ONE hung batch bounds the whole lane
        # rather than the sum of the batches' patience.
        return round_robin([future.result(timeout=RERANK_TIMEOUT)
                            for future in running])
    finally:
        # Not a `with` block: its shutdown waits, which would hold the caller
        # for a hung batch the timeout above just gave up on.
        pool.shutdown(wait=False, cancel_futures=True)
