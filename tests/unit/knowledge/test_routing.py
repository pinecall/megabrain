"""Routing: the shortest path is not the most informative one.

Plain BFS routes through whatever connects fastest, and in a real repository
that is always the logger, the config, or a package `__init__` — a file
imported by half the tree connects ANY pair through infrastructure rather than
through a relationship. Checked live against a general-purpose graph library:
unweighted shortest-path takes exactly that route, because BFS has no concept
of a boring hub.

So transit is COSTED. Hubs, package plumbing and test files pay a toll;
semantic edges cost more than structural ones; the endpoints are free, because
you asked for them.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from megabrain.knowledge.build import load_graph
from megabrain.knowledge.paths import shortest_path
from megabrain.storage import Store


def unit(*values: float) -> np.ndarray:
    raw = np.array(values, dtype=np.float32)
    return raw / np.linalg.norm(raw)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """`a` and `b` are two hops apart through a REAL relationship (`mid`), and
    also two hops apart through `logger`, which everything imports."""
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "mid.py", "logger.py",
                     *(f"noise{n}.py" for n in range(12))):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("a.py", [("mid.py", "import"),
                                           ("logger.py", "import")])
        store.graph.replace_edges("b.py", [("mid.py", "import"),
                                           ("logger.py", "import")])
        # logger is imported by the whole repo — that is what makes it boring
        for n in range(12):
            store.graph.replace_edges(f"noise{n}.py", [("logger.py", "import")])
    return tmp_path


def test_the_route_avoids_the_BORING_hub(repo: Path) -> None:
    """Both routes are two hops. The toll is what breaks the tie, and it has
    to break it towards the relationship rather than the plumbing."""
    hops = shortest_path(load_graph(str(repo)), "a.py", "b.py")
    assert [hop["file"] for hop in hops] == ["a.py", "mid.py", "b.py"]


def test_a_package_init_pays_a_toll_at_ANY_graph_size(tmp_path: Path) -> None:
    """Not degree-dependent: `__init__.py` is plumbing in a five-file repo too,
    and degree cannot see that when the repo is small."""
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "pkg/__init__.py", "real.py"):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("a.py", [("pkg/__init__.py", "import"),
                                           ("real.py", "import")])
        store.graph.replace_edges("b.py", [("pkg/__init__.py", "import"),
                                           ("real.py", "import")])
    hops = shortest_path(load_graph(str(tmp_path)), "a.py", "b.py")
    assert [hop["file"] for hop in hops] == ["a.py", "real.py", "b.py"]


def test_a_test_file_pays_a_toll_too(tmp_path: Path) -> None:
    """Tests bridge everything without explaining anything: they import both
    sides by design, so they are the cheapest route and the least useful."""
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "tests/test_both.py", "real.py"):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("tests/test_both.py",
                                  [("a.py", "import"), ("b.py", "import")])
        store.graph.replace_edges("a.py", [("real.py", "import")])
        store.graph.replace_edges("real.py", [("b.py", "import")])
    hops = shortest_path(load_graph(str(tmp_path)), "a.py", "b.py")
    assert "tests/test_both.py" not in [hop["file"] for hop in hops]


def test_the_ENDPOINTS_are_exempt_from_their_own_toll(tmp_path: Path) -> None:
    """Asking for a route TO the logger must not be penalised for asking."""
    with Store(tmp_path) as store:
        for path in ("a.py", "logger.py", *(f"n{i}.py" for i in range(12))):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("a.py", [("logger.py", "import")])
        for i in range(12):
            store.graph.replace_edges(f"n{i}.py", [("logger.py", "import")])
    hops = shortest_path(load_graph(str(tmp_path)), "a.py", "logger.py")
    assert [hop["file"] for hop in hops] == ["a.py", "logger.py"]


def test_each_hop_names_the_edge_it_crossed(repo: Path) -> None:
    """A route without its reasons is a list of filenames. `via` is what makes
    it a chain: import, call, or semantic — and the reader can tell which."""
    hops = shortest_path(load_graph(str(repo)), "a.py", "b.py")
    assert hops[0]["via"] == ""                      # the start crossed nothing
    assert "import" in str(hops[1]["via"])


def test_a_SEMANTIC_edge_can_carry_a_route_and_says_so(tmp_path: Path) -> None:
    """Structure alone reports "no path" between two files that plainly do the
    same thing. The semantic lane bridges it — and the hop is LABELLED, because
    "related by meaning" and "calls this" are different claims."""
    with Store(tmp_path) as store:
        store.files.upsert("a.py", "s", "x", unit(1, 0))
        store.files.upsert("twin.py", "s", "x", unit(0.999, 0.02))
    hops = shortest_path(load_graph(str(tmp_path)), "a.py", "twin.py")
    assert [hop["file"] for hop in hops] == ["a.py", "twin.py"]
    assert str(hops[1]["via"]).startswith("semantic")


def test_a_structural_edge_is_PREFERRED_over_a_semantic_one(tmp_path: Path) -> None:
    """Both reach b. An import is a fact about execution; a cosine is an
    opinion about wording, and it costs more."""
    with Store(tmp_path) as store:
        store.files.upsert("a.py", "s", "x", unit(1, 0, 0))
        store.files.upsert("b.py", "s", "x", unit(0.999, 0.02, 0))
        store.graph.replace_edges("a.py", [("b.py", "import")])
    hops = shortest_path(load_graph(str(tmp_path)), "a.py", "b.py")
    assert "import" in str(hops[1]["via"])


def test_an_unreachable_target_is_reported_not_invented(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        store.files.upsert("a.py", "sha", "", None)
        store.files.upsert("b.py", "sha", "", None)
    assert shortest_path(load_graph(str(tmp_path)), "a.py", "b.py") == []


def test_the_route_is_deterministic(repo: Path) -> None:
    """Two equal-cost routes must not alternate between runs: a map that
    reshuffles is a map nobody trusts twice."""
    graph = load_graph(str(repo))
    assert shortest_path(graph, "a.py", "b.py") == shortest_path(graph, "a.py", "b.py")
