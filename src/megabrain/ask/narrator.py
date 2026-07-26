"""One narrated walkthrough: retrieve, OPEN what is missing, splice, stream.

The single-agent path, and the fallback for the multi-agent one — a fan-out that
fails must degrade to this rather than to an error.

Retrieval is where the answer STARTS, not all of it: the span that matters can
sit fifty lines below the chunk that matched, so the narrator opens files
(`_converse`) until the question is covered, and `_widen` then adds what readers
kept coming back for. Neither step calls a model twice for the same thing.

Two citation systems meet here, and MEASURED, they were briefly confused with a
serious result. `[[k]]` names a retrieved chunk — spliced as it streams, by
`Splicer`. `[[path:lo-hi]]` names lines of a file the model opened — not
recognised by that splicer at all, so it streamed through as literal brackets;
`broken_references` then saw an unresolved bracket pair, and the repair pass
re-spliced and appended the WHOLE answer a second time. The reader saw the
walkthrough twice. Fixed at the source (`_broken.py` now knows the path form is
not broken) and closed here: ONE quoting pass over the fully assembled text
converts every remaining path citation, from the narration or from `_widen`,
in a single place.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Bundle
from ..providers.chat import ChatProvider
from ..storage import Store
from ._candidates import candidates_of
from ._converse import answered
from ._flowctx import flow_context
from ._grounded import unlinked_hops
from ._quote import quote_citations
from ._rescue import rescue
from ._widen import widen
from .events import Emit, emit_nothing
from .prompt import build_prompt
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
    prompt = build_prompt(question, candidates, flow_context(bundle))
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
    parts.append(widen(answer.text, root))
    parts.append(unlinked_hops(answer.text, candidates, root))
    parts.extend(rescue(provider, answer.text, candidates, emit))
    result = _quoted(root, "".join(parts))
    emit({"type": "narrated", "ms": int((time.perf_counter() - started) * 1000)})
    return result


def _quoted(root: Path | None, text: str) -> str:
    """Every `[[path:lo-hi]]` in `text`, from wherever it came from, spliced.

    Without a `root` there is nothing to splice FROM — the multi-agent path
    narrates that way, and it never opens files either, so this is a no-op.
    """
    if root is None:
        return text
    with Store(root) as store:
        return quote_citations(text, store)
