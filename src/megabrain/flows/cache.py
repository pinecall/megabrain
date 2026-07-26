"""Writing a walkthrough back into the index.

Off the query path entirely: this runs after an ask has already answered, so
its cost is never on anybody's clock. Fail-open throughout — a cache write that
fails must never turn a successful answer into an error.

Two vectors from ONE embedding call: question+prose for the attach lane and the
question alone for the serve lane. One call because the two texts go out
together, and the whole point of the cache is to be cheap.
"""

from __future__ import annotations

from pathlib import Path

from .._arrays import Vector
from ..indexing.passes.embed import Embeddable
from ..storage import Store
from .chrome import strip_chrome
from .freshness import sha_of
from .match import FLOW_DEDUP_SIM

__all__ = ["cache_flow"]


def cache_flow(root: Path | str, question: str, answer: str,
               cited: list[str], embedder: Embeddable) -> bool:
    """Store one answered walkthrough. Returns whether it was written.

    `cited` are the files the answer actually spliced code from — their shas
    are what the flow is pinned to, so it dies with them.
    """
    base = Path(root).expanduser().resolve()
    shas = {relpath: sha_of(base / relpath) for relpath in sorted(set(cited))}
    if not shas or not answer.strip():
        return False
    try:
        attach, serve = _vectors(embedder, question, answer)
        with Store(base) as store:
            _replace_near_duplicates(store, serve)
            store.flows.insert(question=question, text=answer, files=shas,
                               vec=attach, qvec=serve)
    except Exception:                    # noqa: BLE001 — a cache miss is not a failure
        return False
    return True


def _vectors(embedder: Embeddable, question: str,
             answer: str) -> tuple[Vector, Vector]:
    """Both lanes in one call.

    The attach text is the question plus the answer with its citation CHROME
    removed — the block headers are formatting, and letting them into the
    vector makes every flow look alike.
    """
    attach_text = f"{question}\n\n{strip_chrome(answer)}"
    both = embedder.embed([attach_text, question])
    return both[0], both[1]


def _replace_near_duplicates(store: Store, serve: Vector) -> None:
    """The same question asked twice should not accumulate.

    Compared on the SERVE lane, where an identical question scores ~1.0
    regardless of how long either walkthrough became. The newer answer wins
    because it was written against newer code.
    """
    metas, _, existing = store.flows.read_matrix()
    if not metas or not existing.size:
        return
    scores = (existing @ serve + 1) / 2
    store.flows.delete([meta.id for meta, score in zip(metas, scores)
                        if float(score) >= FLOW_DEDUP_SIM])
