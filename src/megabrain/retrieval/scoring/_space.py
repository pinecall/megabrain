"""One query, one index, one vector space.

Its own module because it is the only thing on the read path that can be
wrong about the WHOLE index rather than about one query — and because the
check has to happen between embedding and the first matmul, which is easy to
lose inside the pipeline it guards.
"""

from __future__ import annotations

from ..._arrays import Vector
from ..._errors import ModelMismatch
from ..state import SearchState

__all__ = ["require_same_space"]


def require_same_space(state: SearchState, vector: Vector) -> None:
    """Fail by NAME when the query's model is not the index's.

    Indexing forces a full re-embed when the model changes, but nothing
    guarded the read: pointing a shell at a different `MEGABRAIN_EMBED_MODEL`
    turned every query into a shape error from inside a matmul, which named
    neither model, nor the index, nor the fix.
    """
    stored = int(state.chunks.shape[1])
    if state.chunks.size and vector.size != stored:
        raise ModelMismatch.between(
            query_model=state.embedder.model, query_dims=int(vector.size),
            index_dims=stored, index_model=state.store.graph.get_meta("embed_model"))
