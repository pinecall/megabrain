"""Running the sub-agents at the same time, with a deadline.

The mechanics only. Kept apart from the fan-out's meaning because the two
break for different reasons: the plan can be wrong, and the pool can stall —
and the stall was a real bug that a `with` block reintroduced silently.
"""

from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, as_completed
from typing import TYPE_CHECKING

from ..providers.chat import ChatProvider
from ._subagent import answer_part
from .events import Emit

if TYPE_CHECKING:
    from .agents import Task

__all__ = ["gather", "AGENT_TIMEOUT", "MAX_AGENTS"]

AGENT_TIMEOUT = float(os.environ.get("MEGABRAIN_AGENT_TIMEOUT", "300"))
MAX_AGENTS = int(os.environ.get("MEGABRAIN_MAX_AGENTS", "4"))

Running = "dict[Future[str], Task]"

def gather(provider: ChatProvider, tasks: "list[Task]",
           emit: Emit) -> "list[tuple[Task, str]]":
    """Submit everything, keep whatever finished in time.

    NOT a `with` block: `__exit__` shuts down with `wait=True`, so leaving it
    joins the hung thread and the fan-out stalls for exactly as long as the
    timeout existed to prevent — measured, a 0.15s timeout still took 5.0s.
    `wait=False` bounds the CALLER's wait, which is the honest promise: a
    running Python thread cannot be killed, so a stuck turn lives until its own
    HTTP timeout and simply stops holding up the answer.
    """
    pool = ThreadPoolExecutor(max_workers=min(len(tasks), MAX_AGENTS))
    done: "list[tuple[Task, str]]" = []
    try:
        running = {pool.submit(answer_part, provider, t.sub_query, t.chunks): t
                   for t in tasks}
        for future in _completed(running, emit):
            task = running[future]
            try:
                answer = future.result(timeout=0)
            except Exception as failure:            # noqa: BLE001 — reported, not raised
                emit({"type": "agent", "label": task.label, "state": "failed",
                      "detail": str(failure)})
                continue
            emit({"type": "agent", "label": task.label, "state": "done",
                  "chars": len(answer)})
            done.append((task, answer))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return done


def _completed(running: "dict[Future[str], Task]",
               emit: Emit) -> "list[Future[str]]":
    """Futures in COMPLETION order, giving up on the stragglers.

    `as_completed` raises once the deadline passes, and whatever it has already
    yielded is still good — so the timeout costs the hung members and nothing
    else.
    """
    finished: "list[Future[str]]" = []
    try:
        for future in as_completed(running, timeout=AGENT_TIMEOUT):  # type: ignore[arg-type]
            finished.append(future)
    except TimeoutError:
        stuck = [task.label for future, task in running.items() if future not in finished]
        emit({"type": "agent", "state": "timeout", "labels": stuck})
    return finished
