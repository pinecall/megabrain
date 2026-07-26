"""One narrated walkthrough: retrieve, OPEN what is missing, splice, stream.

The single-agent path, and the fallback for the multi-agent one — a fan-out that
fails must degrade to this rather than to an error.

Retrieval is where the answer STARTS, not all of it: the span that matters can
sit fifty lines below the chunk that matched, so the narrator opens files
(`_converse`) until the question is covered, and `_widen` then adds what readers
kept coming back for. Neither step calls a model twice for the same thing.

Two citation systems meet here and cannot be confused: `[[k]]` names a retrieved
chunk, `[[path:lo-hi]]` names lines of a file the model opened.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Bundle
from ..providers.chat import ChatProvider
from ..storage.model import ChunkMeta
from ._candidates import candidates_of
from ._converse import answered
from ._widen import widen
from .events import Emit, emit_nothing
from .prompt import build_prompt
from .repair import broken_references, repair
from .splice import splice
from .stream import Splicer

__all__ = ["narrate"]

MAX_CANDIDATES = 40


def narrate(provider: ChatProvider, question: str, bundle: Bundle, *,
            root: Path | None = None, emit: Emit = emit_nothing) -> str:
    """Ask, opening files until nothing is missing, and splice every citation."""
    started = time.perf_counter()
    candidates = candidates_of(bundle)
    if not candidates:
        return "no code was retrieved for this question — nothing to walk through"
    prompt = build_prompt(question, candidates, _flow_context(bundle))
    splicer = Splicer(candidates)
    parts: list[str] = []
    emit({"type": "narrating", "candidates": len(candidates)})

    def on_delta(delta: str) -> None:
        if ready := splicer.feed(delta):
            parts.append(ready)
            emit({"type": "delta", "text": ready})

    answer = answered(provider, prompt, root, emit=emit, on_delta=on_delta)
    if tail := splicer.flush():
        parts.append(tail)
        emit({"type": "delta", "text": tail})
    if extra := widen(answer.text, root):
        parts.append(extra)
        emit({"type": "delta", "text": extra})
    parts.extend(_repaired(provider, answer.text, candidates, emit))
    emit({"type": "narrated", "ms": int((time.perf_counter() - started) * 1000)})
    return "".join(parts)


def _repaired(provider: ChatProvider, raw: str, candidates: list[ChunkMeta],
              emit: Emit) -> list[str]:
    """Rescue the references the splice could not resolve.

    Checked against the RAW model output rather than the spliced text: by then
    a resolved citation has become a code block, and what is left is exactly
    what failed. One extra call, only when something broke, and only the broken
    fragments go back — a second full narration would replace prose the reader
    is already reading.
    """
    broken = broken_references(raw)
    if not broken:
        return []
    emit({"type": "repairing", "references": broken})
    fixed = splice(repair(raw, candidates, provider), candidates)
    return [f"\n{fixed}"] if fixed.strip() else []


def _flow_context(bundle: Bundle) -> str:
    """Attached walkthroughs, with their citation chrome removed.

    The chrome must go: shown block headers as context, the model IMITATES
    them — emitting headers instead of citations, so the splicer replaces
    nothing and the answer names files and lines while showing no code.
    """
    from ..flows import strip_chrome

    return "\n\n".join(
        f'Previously asked: "{flow["question"]}"\n{strip_chrome(flow["text"])}'
        for flow in bundle["flows"])
