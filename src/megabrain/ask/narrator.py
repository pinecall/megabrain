"""One narrated walkthrough: retrieve, ask, splice, stream.

The single-agent path. It is also the fallback for the multi-agent one, so it
has to stand on its own — a fan-out that fails must degrade to this rather than
to an error.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Bundle
from ..providers.chat import ChatProvider
from ..storage.model import ChunkMeta
from ._candidates import candidates_of
from .events import Emit, emit_nothing
from .prompt import build_prompt
from .repair import broken_references, repair
from .splice import splice
from .stream import Splicer

__all__ = ["narrate"]

MAX_CANDIDATES = 40


def narrate(provider: ChatProvider, question: str, bundle: Bundle, *,
            root: Path | None = None, emit: Emit = emit_nothing) -> str:
    """Ask once, splice as the answer arrives, return the whole walkthrough."""
    del root                       # the splice reads the index, not the disk
    started = time.perf_counter()
    candidates = candidates_of(bundle)
    if not candidates:
        return "no code was retrieved for this question — nothing to walk through"
    context = _flow_context(bundle)
    splicer = Splicer(candidates)
    parts: list[str] = []
    emit({"type": "narrating", "candidates": len(candidates)})

    def on_delta(delta: str) -> None:
        if ready := splicer.feed(delta):
            parts.append(ready)
            emit({"type": "delta", "text": ready})

    answer = provider.stream_chat(_body(provider, question, candidates, context),
                                  on_delta=on_delta)
    if tail := splicer.flush():
        parts.append(tail)
        emit({"type": "delta", "text": tail})
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


def _body(provider: ChatProvider, question: str, candidates: list[ChunkMeta],
          context: str = "") -> dict[str, object]:
    return {"model": getattr(provider, "model", ""),
            "max_tokens": 2400, "temperature": 0,
            "messages": [{"role": "user",
                          "content": build_prompt(question, candidates, context)}]}


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
