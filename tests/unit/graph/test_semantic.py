"""The semantic lane, and everything downstream of it.

The structural graph alone tells half the story: two files can implement the
same idea and never import each other. The skeleton vectors already exist —
retrieval built them — so the graph gains a second edge type from them, and
three features fall out: better communities (a hub floods label propagation,
a semantic tie resists it), SURPRISES (semantically twins, structurally
strangers), and routes that can cross a gap no import bridges.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from megabrain.graph.build import SEM_EDGE_MIN, load_graph
from megabrain.graph.clusters.communities import communities_of
from megabrain.graph.clusters.surprises import surprises_of
from megabrain.storage import Store


def unit(*values: float) -> np.ndarray:
    raw = np.array(values, dtype=np.float32)
    return raw / np.linalg.norm(raw)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two structural clusters, plus one file semantically TWIN to a file in
    the other cluster — `mirror.py` looks like `auth/login.py` but never
    imports it."""
    with Store(tmp_path) as store:
        vectors = {
            "auth/login.py": unit(1, 0, 0), "auth/token.py": unit(0.98, 0.1, 0),
            "billing/cart.py": unit(0, 1, 0), "billing/invoice.py": unit(0.1, 0.98, 0),
            "mirror.py": unit(0.99, 0.05, 0),          # twin of login, no edge
        }
        for path, vec in vectors.items():
            store.files.upsert(path, "sha", f"skeleton of {path}", vec)
        store.graph.replace_edges("auth/login.py", [("auth/token.py", "import")])
        store.graph.replace_edges("billing/cart.py", [("billing/invoice.py", "import")])
    return tmp_path


def test_semantic_edges_exist_above_the_floor(repo: Path) -> None:
    graph = load_graph(str(repo))
    assert graph.sem["auth/login.py"].get("mirror.py", 0) >= SEM_EDGE_MIN
    assert "billing/cart.py" not in graph.sem["auth/login.py"]


def test_a_semantic_edge_never_counts_as_structure(repo: Path) -> None:
    """`near` is what degree, hubs and orphan-detection read. A cosine tie in
    it would make every similar file look imported."""
    graph = load_graph(str(repo))
    assert "mirror.py" not in graph.near["auth/login.py"]


def test_communities_use_BOTH_lanes(repo: Path) -> None:
    """mirror.py has no imports at all. Structure alone leaves it alone in its
    own community; the semantic tie pulls it into auth's."""
    graph = load_graph(str(repo))
    labels = communities_of(graph)
    assert labels["mirror.py"] == labels["auth/login.py"]
    assert labels["auth/login.py"] != labels["billing/cart.py"]


def test_surprises_are_similar_UNCONNECTED_and_in_different_communities(
        tmp_path: Path) -> None:
    """The definition has three legs and each one excludes something: an edge
    means it is not a surprise, same community means the clustering already
    knows, and low similarity means there is nothing to report.

    The fixture is the subtle part, and the first version of it was wrong: a
    FREE-FLOATING twin merges into its lookalike's community through the
    semantic lane itself, and the third leg then correctly excludes it. A
    genuine surprise needs both sides ANCHORED — a structural tie (weight 1.0)
    outvoting the semantic pull (0.5) — which is precisely the situation worth
    reporting: two subsystems that each have their own life, writing the same
    idea twice.
    """
    with Store(tmp_path) as store:
        store.files.upsert("auth/a.py", "s", "x", unit(1, 0.02, 0))
        store.files.upsert("auth/a2.py", "s", "x", unit(0.7, 0.7, 0))
        store.files.upsert("bill/b.py", "s", "x", unit(0, 0.02, 1))
        store.files.upsert("bill/twin.py", "s", "x", unit(0.999, 0.03, 0.01))
        store.graph.replace_edges("auth/a.py", [("auth/a2.py", "import"),
                                                ("auth/a2.py", "call")])
        store.graph.replace_edges("bill/b.py", [("bill/twin.py", "import"),
                                                ("bill/twin.py", "call")])
    graph = load_graph(str(tmp_path))
    communities = communities_of(graph)
    assert communities["auth/a.py"] != communities["bill/twin.py"], \
        "the fixture must keep the twins in different communities"

    found = surprises_of(graph, communities)
    pairs = {(s["a"], s["b"]) for s in found}
    assert ("auth/a.py", "bill/twin.py") in pairs
    assert not any({"bill/b.py", "bill/twin.py"} == set(pair) for pair in pairs), \
        "an existing edge is not a surprise"


def test_the_map_is_still_byte_stable(repo: Path) -> None:
    graph = load_graph(str(repo))
    assert communities_of(graph) == communities_of(load_graph(str(repo)))

def test_the_full_cosine_matrix_is_not_retained(repo: Path) -> None:
    """Surprise candidates are extracted while the cosines are computed and the
    matrix is DISCARDED: at 10 000 files it is 400 MB of float32 per map call,
    and everything downstream needs only top-k twins above the floor."""
    graph = load_graph(str(repo))
    assert not hasattr(graph, "sims")
    assert any({left, right} == {"auth/login.py", "mirror.py"}
               for left, right, _ in graph.twins)

