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

import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Protocol, Sequence

from ..providers.chat import ChatProvider
from ._verdict import round_robin

if TYPE_CHECKING:
    from ..contracts import Tier2File

__all__ = ["verdict_of", "gathered", "wall_for", "RERANK_BATCH",
           "RERANK_TIMEOUT", "MAX_JUDGES"]

RERANK_BATCH = 8
RERANK_TIMEOUT = 30.0

MAX_JUDGES = 4
"""Concurrent judge calls. A thread per batch is unbounded in the number of
batches; tier-2 is ~20 entries today, so four covers it without letting a
bigger tier open a thread — and a connection — per eight files."""


def wall_for(provider: ChatProvider) -> float:
    """How long one batch may take, asked OF THE BACKEND.

    Fixed at the HTTP number, the wall starved the SDK backend even after its
    own timeout was set right: a CLI spawn eats ~14 s before the first token,
    so every batch died at 30 and the fail-open lane went dark — silently,
    which is the worst way. A backend that carries a `timeout` knows its own
    cost; one that does not gets the measured HTTP wall.
    """
    held = getattr(provider, "timeout", None)
    return float(held) if held else RERANK_TIMEOUT


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
    pool = ThreadPoolExecutor(max_workers=min(len(batches), MAX_JUDGES))
    try:
        running = [pool.submit(judge, provider, question, batch, start)
                   for batch, start in zip(batches, offsets)]
        return round_robin(gathered(running, wall_for(provider)))
    finally:
        # Not a `with` block: its shutdown waits, which would hold the caller
        # for a hung batch the timeout above just gave up on.
        pool.shutdown(wait=False, cancel_futures=True)


def gathered(running: Sequence[Any], wall: float,
             clock: Callable[[], float] = time.monotonic) -> list[Any]:
    """Every result under ONE deadline, so a hung batch bounds the whole lane.

    A per-future `result(timeout=wall)` restarts the wall for each one — k
    staggered slow batches then cost ~k×wall, which is exactly the sum of
    patience the comment above promises not to pay. The deadline is computed
    once; each wait gets only what the earlier ones left.
    """
    deadline = clock() + wall
    out: list[Any] = []
    for future in running:
        left = deadline - clock()
        if left <= 0:
            raise TimeoutError(f"the lane's {wall:.0f}s wall is spent")
        out.append(future.result(timeout=left))
    return out
