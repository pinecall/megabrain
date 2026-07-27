"""The bundle v3 ITSELF assembles must satisfy the contract it declares.

Every other shape check in this suite runs against captured fixtures — payloads
the OLD engine produced. That proves the contract describes the past; it says
nothing about the present. The gap is exactly how a producer violation shipped
green once already: `Tier1File.symbols` was filled with raw storage rows
(seven keys, including an undocumented `decorators`) laundered past the type
checker with an identity list-comp and a `type: ignore`. No fixture could see
it, because no fixture came from this engine.

This test closes that loop: assemble a bundle from a real in-memory index and
run it through the same strict validator the fixtures get.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from megabrain.contracts import Bundle
from megabrain.search.bundle import search_with_state
from megabrain.search.state import SearchState
from megabrain.storage import Store
from tests.contracts.shape import assert_shape
from tests.unit.storage.factories import chunk, symbol


@pytest.fixture
def state(tmp_path: Path) -> SearchState:
    """A tiny real index: two files, three chunks, symbols with decorators.

    The decorators matter — they are the field that leaked. A fixture without
    them would pass even against the buggy producer.
    """
    with Store(tmp_path) as store:
        store.chunks.insert(
            [chunk("svc.py", cid=1, start=1, end=10, name="Service.handle"),
             chunk("svc.py", cid=2, start=11, end=20, name="Service.close"),
             chunk("util.py", cid=3, start=1, end=8, name="helper")],
            np.eye(3, 4, dtype=np.float32))
        store.symbols.insert(
            [symbol("svc.py", name="Service.handle", decorators=("property",)),
             symbol("util.py", name="helper")])
        store.files.upsert("svc.py", "sha-a", "class Service", np.ones(4, np.float32))
        store.files.upsert("util.py", "sha-b", "def helper", np.ones(4, np.float32))
        store.commit()
        metas, chunks = store.chunks.read_matrix()
        paths, skels, files = store.files.read_matrix()
    # Reopen read-only for the query; the state owns this connection.
    store = Store(tmp_path)

    class _StubEmbedder:
        model = "stub"

        def embed(self, texts, *, on_batch=None):  # type: ignore[no-untyped-def]
            return [np.ones(4, dtype=np.float32) / 2.0 for _ in texts]

    return SearchState(store=store, embedder=_StubEmbedder(),  # type: ignore[arg-type]
                       metas=metas, chunks=chunks, file_paths=paths,
                       file_skeletons=skels, files=files, repo="probe")


def test_an_assembled_bundle_satisfies_the_declared_contract(state: SearchState) -> None:
    with state:
        bundle = search_with_state(state, "how does Service handle requests")
    assert_shape(bundle, Bundle)


def test_core_symbols_are_the_outline_shape_not_raw_storage_rows(state: SearchState) -> None:
    """The specific leak, pinned by name.

    Storage rows carry `decorators`; the `SymbolRef` contract does not. The
    tier-2 path already narrows through `to_outline`; tier-1 must take the
    same door — a second, wider door is how the two drift.
    """
    with state:
        bundle = search_with_state(state, "how does Service handle requests")
    for tier in bundle["tier1"]:
        for entry in tier["symbols"]:
            assert "decorators" not in entry, f"{tier['file']}: raw storage row leaked"
