"""The dependency graph: clusters, hubs, neighbourhoods, paths.

Everything here is DISPLAY or NAVIGATION. If any of it ever starts ranking,
the experiment that settled hard rule #3 has to be re-run first — PageRank as
a ranking signal dropped Acc@1 from 0.91 to 0.73.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.graph import graph_map, graph_path, neighbourhood
from megabrain.storage import Store


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two clusters joined by a single bridge.

    auth/{login,session,token} import each other; billing/{cart,invoice} do
    the same; `app.py` imports one file from each. A clustering that cannot
    see two groups here cannot see them anywhere.
    """
    with Store(tmp_path) as store:
        for path in ("auth/login.py", "auth/session.py", "auth/token.py",
                     "billing/cart.py", "billing/invoice.py", "app.py"):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("auth/login.py", [("auth/session.py", "import"),
                                                    ("auth/token.py", "import"),
                                                    ("auth/token.py", "call")])
        store.graph.replace_edges("auth/session.py", [("auth/token.py", "import")])
        store.graph.replace_edges("billing/cart.py", [("billing/invoice.py", "import")])
        store.graph.replace_edges("billing/invoice.py", [("billing/cart.py", "call")])
        store.graph.replace_edges("app.py", [("auth/login.py", "import"),
                                             ("billing/cart.py", "import")])
    return tmp_path


def test_the_map_carries_every_indexed_file(repo: Path) -> None:
    """Including the ones with no edges: a file nobody imports is exactly what
    someone opens the graph to find."""
    result = graph_map(repo)
    assert result["files"] == 6
    assert {n["file"] for n in result["nodes"]} == {
        "auth/login.py", "auth/session.py", "auth/token.py",
        "billing/cart.py", "billing/invoice.py", "app.py"}


def test_two_kinds_between_the_same_pair_are_ONE_link(repo: Path) -> None:
    """login imports AND calls token. Drawn twice it reads as two
    dependencies, so the kinds are joined onto one edge."""
    links = [link for link in graph_map(repo)["links"]
             if {link["source"], link["target"]} == {"auth/login.py", "auth/token.py"}]
    assert len(links) == 1
    assert links[0]["kind"] == "call/import"


def test_the_clusters_are_found(repo: Path) -> None:
    communities = graph_map(repo)["communities"]
    grouped = {frozenset(c["files"]) for c in communities}
    assert any({"auth/login.py", "auth/session.py", "auth/token.py"} <= set(g)
               for g in grouped), grouped
    assert any({"billing/cart.py", "billing/invoice.py"} <= set(g)
               for g in grouped), grouped


def test_communities_are_numbered_by_size_largest_first(repo: Path) -> None:
    """Numbered by size rather than by iteration order, so the same repo
    produces the same numbering every run."""
    sizes = [c["size"] for c in graph_map(repo)["communities"]]
    assert sizes == sorted(sizes, reverse=True)
    assert [c["id"] for c in graph_map(repo)["communities"]] == list(range(len(sizes)))


def test_the_map_is_byte_stable_across_runs(repo: Path) -> None:
    """Label propagation visits in a fixed order and breaks ties on the
    smallest label. Without both, the clusters shuffle between runs and a
    diff of two maps is unreadable."""
    assert graph_map(repo)["communities"] == graph_map(repo)["communities"]
    assert graph_map(repo)["nodes"] == graph_map(repo)["nodes"]


def test_hubs_are_what_others_DEPEND_on(repo: Path) -> None:
    """Ranked by in-degree, not by degree: a file that imports twenty others
    is busy, a file twenty others import is load-bearing."""
    hubs = graph_map(repo)["hubs"]
    assert hubs[0]["file"] == "auth/token.py", hubs
    assert hubs[0]["in_degree"] == 2


def test_a_neighbourhood_shows_both_directions(repo: Path) -> None:
    view = neighbourhood(repo, "auth/token.py")
    assert view["imports"] == []
    assert view["imported_by"] == ["auth/login.py", "auth/session.py"]


def test_a_neighbourhood_of_an_unknown_file_says_so(repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="nope.py"):
        neighbourhood(repo, "nope.py")


def test_a_path_crosses_the_bridge(repo: Path) -> None:
    """The question a graph answers that nothing else does: HOW are these two
    connected. The only route here runs through app.py."""
    result = graph_path(repo, "auth/session.py", "billing/invoice.py")
    walked = [hop["file"] for hop in result["hops"]]
    assert result["found"] is True
    assert walked[0] == "auth/session.py" and walked[-1] == "billing/invoice.py"
    assert "app.py" in walked


def test_a_path_to_an_unconnected_file_is_reported_not_invented(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        store.files.upsert("a.py", "sha", "", None)
        store.files.upsert("b.py", "sha", "", None)
    result = graph_path(tmp_path, "a.py", "b.py")
    assert result["found"] is False and result["hops"] == []


def test_a_path_to_itself_is_one_hop(repo: Path) -> None:
    hops = graph_path(repo, "app.py", "app.py")["hops"]
    assert [hop["file"] for hop in hops] == ["app.py"]


def test_the_shortest_path_is_the_one_returned(tmp_path: Path) -> None:
    """A long way round exists; BFS must not take it."""
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "c.py", "d.py"):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("a.py", [("b.py", "import"), ("d.py", "import")])
        store.graph.replace_edges("b.py", [("c.py", "import")])
        store.graph.replace_edges("d.py", [("c.py", "import")])
    assert len(graph_path(tmp_path, "a.py", "c.py")["hops"]) == 3
