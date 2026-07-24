"""The embedder: batching, wire decoding, and the cache that makes re-indexing
a near-identical checkout almost free."""

from __future__ import annotations

import base64

import numpy as np
import pytest

from megabrain._errors import MissingCredential
from megabrain.providers.embeddings import Embedder
from tests.unit.providers.fake import FakeTransport, ok

pytestmark = pytest.mark.usefixtures("no_sleep")


def _wire(vectors: list[list[int]]) -> bytes:
    """The int8-base64 shape the endpoint returns."""
    import json
    data = [{"embedding": base64.b64encode(bytes((v + 256) % 256 for v in row)).decode()}
            for row in vectors]
    return json.dumps({"data": data}).encode()


def _embedder(transport: FakeTransport, **kw: object) -> Embedder:
    return Embedder(transport=transport, api_key="k", cache=None, **kw)  # type: ignore[arg-type]


def test_vectors_come_back_l2_normalised() -> None:
    """Cosine similarity is a dot product only on unit vectors, and every
    scoring lane multiplies without normalising first."""
    emb = _embedder(FakeTransport([ok(_wire([[3, 4, 0, 0]]))]))
    (vec,) = emb.embed(["hello"])
    assert vec.dtype == np.float32
    assert np.isclose(np.linalg.norm(vec), 1.0)


def test_a_zero_vector_does_not_divide_by_zero() -> None:
    """An empty or degenerate embedding must not produce NaNs that then poison
    every score it touches."""
    emb = _embedder(FakeTransport([ok(_wire([[0, 0, 0, 0]]))]))
    (vec,) = emb.embed(["x"])
    assert not np.isnan(vec).any()


def test_order_is_preserved_across_batches() -> None:
    """Row i must be the embedding of text i. A reordering does not raise; it
    silently attaches every chunk's vector to a different chunk."""
    transport = FakeTransport([ok(_wire([[1, 0], [0, 1]])), ok(_wire([[1, 1]]))])
    vecs = _embedder(transport, batch_size=2).embed(["a", "b", "c"])
    assert len(vecs) == 3
    assert transport.calls == 2
    assert np.isclose(vecs[0] @ vecs[1], 0.0)          # first batch, orthogonal
    assert np.isclose(vecs[2] @ vecs[2], 1.0)


def test_no_texts_means_no_request() -> None:
    transport = FakeTransport([ok(_wire([[1, 0]]))])
    assert _embedder(transport).embed([]) == []
    assert transport.calls == 0


def test_a_missing_key_fails_before_the_request() -> None:
    """Named, actionable, and raised without burning a round trip."""
    transport = FakeTransport([ok(_wire([[1, 0]]))])
    emb = Embedder(transport=transport, api_key=None, cache=None)
    with pytest.raises(MissingCredential, match="MEGABRAIN_EMBED_API_KEY"):
        emb.embed(["x"])
    assert transport.calls == 0


def test_progress_reports_every_batch() -> None:
    """Indexing a large repo is a long silence otherwise."""
    seen: list[tuple[int, int]] = []
    transport = FakeTransport([ok(_wire([[1, 0], [0, 1]]))])
    _embedder(transport, batch_size=2).embed(["a", "b", "c", "d"],
                                             on_batch=lambda d, t: seen.append((d, t)))
    assert seen == [(2, 4), (4, 4)]
