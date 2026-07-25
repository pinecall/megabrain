"""The brief: the mental model for a question — deterministic, no LLM, ever.

Selection is NOT a second engine. The deterministic bundle already defines
which files answer a question — chunk+skeleton fusion, the test penalty, the
two recall floors, every number measured, invariant #2 enforced. The brief
takes that selection and changes only the PRESENTATION: the model-written card
instead of code bodies, relations rendered live from the graph, interfaces
from the symbol table.

A first draft ranked on one vector per card instead, and paid for it on a real
corpus: a card that averages a file's seven responsibilities buried the
validation pipeline at rank 5, below a file that merely shared the question's
vocabulary. Ranking is the engine's job; the atlas only narrates.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .._errors import StudyNotFound
from ..contracts import Brief, Bundle
from ..knowledge.build import load_graph
from ..retrieval.bundle import search_with_state
from ..retrieval.state import load_state
from ._assemble import entry_of, narrative_order

__all__ = ["brief_repo"]

DEFAULT_LIMIT = 10


def brief_repo(root: Path, question: str, *, limit: int = DEFAULT_LIMIT,
               embedder: object = None,
               judge: Callable[[Bundle], Bundle] | None = None) -> Brief:
    """Answer `question` with the mental model: cards, relations, interfaces.

    `judge` reorders the bundle before selection — the same judge lane search
    offers, injected rather than imported so this layer stays deterministic
    and model-free by construction. Policy (which model, whether to spend the
    call) lives with the caller, exactly as the module docstring demands:
    ranking is the engine's job, the atlas only narrates.
    """
    started = time.perf_counter()
    graph = load_graph(str(root))
    state = load_state(root)
    if embedder is not None:
        state.embedder = embedder  # type: ignore[assignment]  # test seam, as in `search`
    with state:
        if not state.store.cards.count():
            raise StudyNotFound(f"no study cards at {root} — "
                                f"run `megabrain study` once")
        bundle = search_with_state(state, question)
        if judge is not None:
            bundle = judge(bundle)
        ranked = _selection(bundle)[:limit]
        cards = state.store.cards.read_for([relpath for relpath, _ in ranked])
        skeletons = dict(zip(state.file_paths, state.file_skeletons))
        scores = dict(ranked)
        entries = [entry_of(state.store, graph, relpath,
                            *_card(cards, skeletons, relpath), scores[relpath])
                   for relpath in narrative_order([f for f, _ in ranked], graph)]
        considered = len(state.file_paths)
    return {"repo": bundle["repo"], "query": question, "files": entries,
            "considered": considered,
            "ms": int((time.perf_counter() - started) * 1000)}


def _selection(bundle: Bundle) -> list[tuple[str, float]]:
    """The bundle's files in the bundle's order: CORE first, then RELATED.

    Deduped by first appearance — a file can rank in tier 1 and be reached
    again by a floor, and the reader should meet it once, at its best rank.
    """
    out: list[tuple[str, float]] = []
    seen: set[str] = set()
    for entry in [*bundle["tier1"], *bundle["tier2"]]:
        relpath = entry["file"]
        if relpath not in seen:
            seen.add(relpath)
            out.append((relpath, float(entry["score"])))
    return out


def _card(cards: dict[str, tuple[str, bool]], skeletons: dict[str, str],
          relpath: str) -> tuple[str, bool]:
    """The stored card, or the skeleton marked degraded.

    The bundle may pick a file `study` had nothing to say about — nothing
    declared, or indexed after the last study. The skeleton is the same
    zero-lies fallback the author uses, so the brief never shows an empty
    entry for a file retrieval judged relevant.
    """
    if relpath in cards:
        return cards[relpath]
    return skeletons.get(relpath, ""), True
