"""Fanning out: plan, run sub-agents in PARALLEL, synthesise.

Why parallel and not one long turn: a broad question ("how does auth work")
covers several mechanisms, and one model reading forty chunks writes a summary
of all of them. Split it — one sub-agent per mechanism, each with its own
chunks — and each answer is specific. They are independent by construction, so
they run at the same time and the walkthrough costs the SLOWEST sub-agent
rather than the sum.

A hung sub-agent dies alone and the rest proceed. That is the whole reason for
the timeout: a fan-out where one stuck member blocks the answer is worse than
no fan-out, because it fails slower than the thing it replaced.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ...events import Emit, emit_nothing
from ...providers.chat import ChatProvider
from ...storage.model import ChunkMeta
from ._pool import gather

__all__ = ["Task", "run_agents"]

@dataclass(frozen=True, slots=True)
class Task:
    """One sub-agent's job: a label, a narrower question, its own chunks."""

    label: str
    sub_query: str
    chunks: list[ChunkMeta]


def run_agents(provider: ChatProvider, tasks: list[Task], *,
               emit: Emit = emit_nothing) -> list[tuple[Task, str]]:
    """Every task, at the same time. Returns the ones that answered.

    A sub-agent that fails or times out is DROPPED, not raised: the others did
    real work, and throwing it away because one member stalled turns a partial
    answer into no answer. The caller decides whether what came back is enough.
    """
    if not tasks:
        return []
    emit({"type": "plan", "agents": [{"label": t.label, "sub_query": t.sub_query,
                                      "chunks": len(t.chunks)} for t in tasks]})
    started = time.perf_counter()
    done = gather(provider, tasks, emit)
    emit({"type": "agent", "state": "all",
          "answered": len(done), "of": len(tasks),
          "ms": int((time.perf_counter() - started) * 1000)})
    return done
