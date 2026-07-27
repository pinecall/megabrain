"""Wiring the flow cache into `ask`: serve, attach, re-cache.

Kept out of `ask` itself so the verb stays readable as the three steps it is —
retrieve, explain, answer — while the caching decisions live where their
reasons are written down.
"""

from __future__ import annotations

from pathlib import Path

from ..ask.events import Emit
from ..contracts import Bundle, FlowHit
from ..flows import cache_flow, match_flows, serve_verbatim
from ..search.state import load_state

__all__ = ["matched_flows", "served", "remember_answer", "FLOW_FILE_ADDS"]

FLOW_FILE_ADDS = 3
"""How many of a flow's source files may be appended to RELATED.

Appended only when MISSING, and appended only — a flow never reorders and never
displaces a file. That is the recall floors' rule applied here: the bundle can
only gain, so completeness cannot fall because a cache had an opinion.
"""


def matched_flows(root: Path, question: str) -> list[FlowHit]:
    """The cached walkthroughs this question pulls in. Cosine only.

    Re-embeds the question rather than reusing the bundle's vector: the bundle
    may have come from a caller that scored it earlier, and a flow matched
    against somebody else's query is the subtlest wrong answer here.
    """
    with load_state(root) as state:
        metas, attach, serve = state.store.flows.read_matrix()
        if not metas:
            return []
        query = state.embedder.embed([question])[0]
    return match_flows(metas, attach, serve, query)


def served(root: Path, question: str, flows: list[FlowHit],
           emit: Emit) -> FlowHit | None:
    """A cached answer good enough to return AS the answer, or None."""
    hit = serve_verbatim(root, flows, question)
    if hit is None:
        return None
    emit({"type": "cached", "question": hit["question"],
          "qscore": hit["qscore"], "files": hit["files"]})
    # The cached text goes out as a DELTA, exactly like a fresh one. Every
    # surface renders the answer from the event stream, so a cache that
    # returned quietly printed nothing at all — measured: the second ask
    # answered in 0.2s and showed an empty screen.
    emit({"type": "delta", "text": hit["text"]})
    emit({"type": "narrated", "ms": 0, "cached": True})
    return hit


def remember_answer(root: Path, question: str, answer: str,
                    bundle: Bundle, emit: Emit) -> None:
    """Cache a fresh walkthrough, pinned to the files it actually cited.

    The cited set is taken from the BUNDLE, not parsed out of the prose: the
    splice already resolved every citation to a real chunk, and re-deriving it
    from text would be a second parser to keep in step with the first.
    """
    cited = [entry["file"] for entry in bundle["tier1"]]
    with load_state(root) as state:
        embedder = state.embedder
    if cache_flow(root, question, answer, cited, embedder):
        emit({"type": "cached_write", "files": sorted(set(cited))})
