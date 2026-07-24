"""Retrieval findings from the audit round.

Retrieval's contract is that the same index and the same query give the same
answer. Every finding here is a way that quietly stopped being true — a tie
broken by whichever order numpy felt like, a neighbour list ordered by a set,
a query that crashes on an index nobody thought to build.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from megabrain.retrieval.bundle._rank import rank_files
from megabrain.retrieval.scoring.pipeline import score_chunks
from megabrain.storage.model import ChunkMeta

ROOT = Path(__file__).resolve().parents[3]


def _meta(chunk_id: int, relpath: str) -> ChunkMeta:
    return ChunkMeta(id=chunk_id, file=relpath, kind="function", name=f"f{chunk_id}",
                     part=None, start_line=1, end_line=2, text="pass",
                     breadcrumb=f"{relpath}::f{chunk_id}")


def test_tied_chunks_rank_in_index_order() -> None:
    """numpy's default sort is introsort: on ties it returns whatever its
    partitioning produced, which changes with array size and numpy version.

    Retrieval promises the same answer for the same index. Scores tie all the
    time — a file whose chunks are near-identical, a query matching nothing in
    particular — and an unstable sort turns that into a ranking that reshuffles
    for no reason a reader can see.
    """
    metas = [_meta(i, f"f{i:03d}.py") for i in range(200)]
    fused = np.zeros(200, dtype=np.float32)
    fused[:100] = 1.0

    order = rank_files(metas, fused).order

    assert order[:100] == [m.file for m in metas[:100]], "ties were reordered"


def test_scoring_returns_the_query_vector_it_computed() -> None:
    """The vector has to travel WITH the scores.

    Stashing it on the shared state made every later stage trust that whoever
    scored last scored THIS query — an invariant nothing checks and a second
    caller silently breaks. Carrying it in the result makes the dependency a
    parameter instead of a convention.
    """
    from megabrain.retrieval.scoring.pipeline import Scored

    assert set(Scored.__dataclass_fields__) == {"metas", "fused", "query_vector"}


def test_an_index_with_no_file_skeletons_still_answers(tmp_path: Path) -> None:
    """Chunks embedded, skeletons not — every file-level vector missing.

    The fusion lane indexes the file matrix with the per-chunk join, and numpy
    evaluates BOTH branches of a where(), so the -1 sentinel reached an empty
    matrix and the query died with a shape error instead of scoring on the
    chunk signal alone.
    """
    from tests.unit.retrieval.factories import index_without_skeletons

    with index_without_skeletons(tmp_path) as state:  # noqa: SIM117
        scored = score_chunks(state, "how does the service handle requests")

    assert len(scored.fused) == len(scored.metas) > 0


def test_neighbour_order_does_not_depend_on_the_hash_seed() -> None:
    """`reachable & set(order)` is a SET, and its iteration order comes from
    salted string hashes. Sorting it by score alone is stable with respect to
    THAT order, so tied neighbours came out differently in every process — the
    same query, the same index, a different bundle.
    """
    code = ("from tests.unit.retrieval.factories import tied_neighbours;"
            "print(tied_neighbours())")
    runs = {subprocess.run([sys.executable, "-c", code], check=True, text=True,
                           capture_output=True, cwd=str(ROOT),
                           env={"PYTHONHASHSEED": str(seed), "PATH": "/usr/bin:/bin"}).stdout
            for seed in (0, 1)}
    assert len(runs) == 1, f"neighbour order changed with the hash seed: {runs}"


@pytest.mark.parametrize("query", ["", "   ", "?"])
def test_a_contentless_query_is_answered_not_crashed(tmp_path: Path, query: str) -> None:
    """No identifiers to boost and nothing to match: the lexical lane must
    self-gate rather than build a boost array against an empty token set."""
    from tests.unit.retrieval.factories import small_index

    with small_index(tmp_path) as state:
        assert len(score_chunks(state, query).fused) == len(state.metas)
