"""The three views, assembled.

Assembly only — every number in them was computed by `build`, `communities`,
`gods`, `surprises`, `paths` or `story`. What is tested here is that the view
carries all of it, because a map missing its god nodes or a route missing its
code is the difference between a picture and an answer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.knowledge import graph_map, graph_node, graph_path
from megabrain.usecases import build_index
from tests.unit.indexing.fake import write
from tests.unit.knowledge.fake import WordEmbedder

TWIN = ("def login():\n    return authenticate_user_session()\n\n\n"
        "def authenticate_user_session():\n    return True\n")

FILES = {
    "app.py": "from .auth import login\nfrom .billing import charge\n\n\n"
              "def main():\n    login()\n    charge()\n",
    "auth.py": TWIN,
    "billing.py": "def charge():\n    return 1\n",
    # `mirror.py` is `auth.py` written twice, and ANCHORED in its own corner of
    # the repo — a free-floating twin gets absorbed into its lookalike's
    # community through the semantic lane, and then is correctly not a surprise.
    "legacy/mirror.py": TWIN,
    "legacy/entry.py": "from .mirror import login\n\n\ndef entry():\n    return login()\n",
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, FILES)
    build_index(tmp_path, embedder=WordEmbedder())
    return tmp_path


def test_the_map_names_its_communities(repo: Path) -> None:
    """With no provider configured the label falls back — but it EXISTS, so the
    studio never renders a legend of bare integers."""
    whole = graph_map(repo)
    assert all(community["label"] for community in whole["communities"])


def test_the_map_reports_god_nodes_with_the_direction_split(repo: Path) -> None:
    """`app.py` imports both sides: out-degree 2, in-degree 0. The split is the
    diagnosis — an orchestrator is not a load-bearing module."""
    gods = {node["file"]: node for node in graph_map(repo)["god_nodes"]}
    assert gods["app.py"]["out_degree"] == 2
    assert gods["app.py"]["in_degree"] == 0
    assert gods["auth.py"]["in_degree"] == 1


def test_the_map_reports_SURPRISES(repo: Path) -> None:
    """`legacy/mirror.py` is `auth.py` written twice, in a corner of the repo
    that never talks to it. Nothing the map DRAWS shows that — there is no edge
    to draw — so it has to be said in words."""
    pairs = {frozenset((s["a"], s["b"])) for s in graph_map(repo, label=False)["surprises"]}
    assert frozenset(("auth.py", "legacy/mirror.py")) in pairs


def test_the_map_draws_semantic_links_LABELLED_as_such(repo: Path) -> None:
    """Drawing a cosine as if it were an import is the one thing the map must
    never do: the reader would go looking for a call that does not exist."""
    links = graph_map(repo)["links"]
    semantic = [link for link in links if link["kind"] == "semantic"]
    assert semantic and all(0.0 <= link["score"] <= 1.0 for link in semantic)
    assert all(link["kind"] != "semantic" or "import" not in link["kind"]
               for link in links)


def test_a_node_view_answers_for_a_TERM_not_only_a_path(repo: Path) -> None:
    view = graph_node(repo, "auth", embedder=WordEmbedder())
    assert view["file"] == "auth.py" and view["resolved_from"] == "auth"


def test_a_node_view_carries_both_directions_and_its_twins(repo: Path) -> None:
    view = graph_node(repo, "auth.py", embedder=WordEmbedder())
    assert {edge["file"] for edge in view["imported_by"]} == {"app.py"}
    assert "legacy/mirror.py" in [tie["file"] for tie in view["semantic"]]
    assert any(symbol["name"] == "login" for symbol in view["symbols"])


def test_the_incoming_edges_keep_their_KINDS_apart(repo: Path) -> None:
    """`app.py` both imports `login` and calls it. Merged into one entry the
    node view loses the distinction somebody opened it to see."""
    view = graph_node(repo, "auth.py", embedder=WordEmbedder())
    assert {edge["kind"] for edge in view["imported_by"]} == {"import", "call"}


def test_a_node_view_of_an_EMPTY_index_says_so(tmp_path: Path) -> None:
    """Concept resolution always has a nearest file, so the only term that
    genuinely matches nothing is any term at all against an empty index — and
    that must be an error, not the first path in an empty list."""
    write(tmp_path, {"notes.txt": "no code here\n"})
    build_index(tmp_path, embedder=WordEmbedder())
    with pytest.raises(FileNotFoundError):
        graph_node(tmp_path, "anything", embedder=WordEmbedder())


def test_a_route_carries_the_carrier_symbols_and_the_code(repo: Path) -> None:
    """The whole reason the route is worth more than a list of filenames."""
    route = graph_path(repo, "app.py", "auth.py", embedder=WordEmbedder())
    assert route["found"] is True
    assert route["hops"][-1]["symbols"] == ["login"]
    assert (route["hops"][-1]["code"] or {})["verified"] is True


def test_a_route_between_two_TERMS_resolves_both_ends(repo: Path) -> None:
    route = graph_path(repo, "app", "billing", embedder=WordEmbedder())
    assert route["source"] == "app.py" and route["target"] == "billing.py"


def test_an_unreachable_route_reports_not_found_without_inventing_hops(
        repo: Path) -> None:
    write(repo, {"island.py": "def alone():\n    return 0\n"})
    build_index(repo, embedder=WordEmbedder())
    route = graph_path(repo, "island.py", "billing.py", embedder=WordEmbedder())
    assert route["found"] is False and route["hops"] == []


def test_the_route_says_whether_it_is_a_chain(repo: Path) -> None:
    route = graph_path(repo, "auth.py", "billing.py", embedder=WordEmbedder())
    assert route["chain"] is False and route["meet"] == "app.py"
    assert route["meet_kind"] == "caller"        # app.py calls BOTH sides
