"""Querying an index with a different embedding model than built it.

The index guards this when it WRITES (a model change forces a re-embed), but
nothing guarded the read. Point a shell at a different `MEGABRAIN_EMBED_MODEL`
and every query died inside numpy with

    ValueError: matmul: Input operand 1 has a mismatch in its core dimension 0,
    with gufunc signature (n?,k),(k,m?)->(n?,m?) (size 1024 is different from 4)

which names neither the model, nor the index, nor what to do about it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pytest

from megabrain._errors import ModelMismatch
from megabrain.retrieval.scoring.pipeline import score_chunks


class _WiderEmbedder:
    """A model returning a different width than the one that built the index."""

    model = "some-other-embed-model"

    def embed(self, texts: Sequence[str], *, on_batch: object = None) -> list[np.ndarray]:
        return [np.ones(1024, dtype=np.float32) / 32 for _ in texts]


def test_a_mismatched_query_model_is_named_not_a_numpy_traceback(tmp_path: Path) -> None:
    from tests.unit.retrieval.factories import small_index

    with small_index(tmp_path) as state:
        state.embedder = _WiderEmbedder()          # type: ignore[assignment]
        with pytest.raises(ModelMismatch) as caught:
            score_chunks(state, "anything")

    message = str(caught.value)
    assert "1024" in message and "4" in message, "the two widths must both be named"
    assert "megabrain index" in message, "it has to say how to fix it"


def test_the_matching_case_is_untouched(tmp_path: Path) -> None:
    """The guard must not cost a working query anything but a comparison."""
    from tests.unit.retrieval.factories import small_index

    with small_index(tmp_path) as state:
        assert len(score_chunks(state, "anything").fused) == len(state.metas)
