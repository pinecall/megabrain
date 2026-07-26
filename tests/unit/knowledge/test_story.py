"""Turning a route into a story that is TRUE.

Two ways a plain route lies to a reader.

The graph is undirected, so a question phrased against the flow ("scoring →
narrator" when the calls run narrator → agents → scoring) walks every call
backwards, and the rendered chain reads as if the dependency ran the other way.

Worse: a route through a shared callee is not a flow at all. `scoring → http ←
rerank` means both files call INTO http and never into each other. Presented as
"scoring reaches rerank through http" it invents a relationship. It has to be
named for what it is — a meeting point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.knowledge.routes.story import orient_hops, tell
from megabrain.storage import Store
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write

# narrator calls agents, agents calls scoring — a real chain, one direction.
CHAIN = {
    "narrator.py": "from .agents import dispatch\n\n\ndef narrate(q):\n"
                   "    return dispatch(q)\n",
    "agents.py": "from .scoring import fuse\n\n\ndef dispatch(q):\n"
                 "    return fuse(q)\n",
    "scoring.py": "def fuse(q):\n    return q\n",
}

# scoring and rerank BOTH call into http, and never into each other.
MEETING = {
    "http.py": "def post(body):\n    return body\n",
    "scoring.py": "from .http import post\n\n\ndef fuse(q):\n"
                  "    return post(q)\n",
    "rerank.py": "from .http import post\n\n\ndef judge(q):\n"
                 "    return post(q)\n",
}


def indexed(root: Path, files: dict[str, str]) -> Path:
    write(root, {**files, "__init__.py": ""})
    build_index(root, embedder=CountingEmbedder())
    return root


@pytest.fixture
def chain(tmp_path: Path) -> Path:
    return indexed(tmp_path, CHAIN)


@pytest.fixture
def meeting(tmp_path: Path) -> Path:
    return indexed(tmp_path, MEETING)


def story(root: Path, source: str, target: str) -> dict[str, object]:
    hops = [{"file": source, "via": ""}, *({"file": relpath, "via": "import"}
                                           for relpath in _between(source, target))]
    with Store(root) as store:
        return tell(store, root, hops)


def _between(source: str, target: str) -> list[str]:
    """The middle of the fixture routes, spelled out — this module tests the
    STORY, not the routing, so the route is given rather than computed."""
    routes = {("narrator.py", "scoring.py"): ["agents.py", "scoring.py"],
              ("scoring.py", "narrator.py"): ["agents.py", "narrator.py"],
              ("scoring.py", "rerank.py"): ["http.py", "rerank.py"]}
    return routes[(source, target)]


def test_a_real_chain_is_reported_as_a_chain(chain: Path) -> None:
    told = story(chain, "narrator.py", "scoring.py")
    assert told["chain"] is True and told["meet"] is None


def test_a_shared_CALLEE_is_reported_as_a_meeting_not_a_flow(meeting: Path) -> None:
    """The finding worth having. Both ends call into `http`; there is no chain
    to tell, and saying so is more useful than a route that reads like one."""
    told = story(meeting, "scoring.py", "rerank.py")
    assert told["chain"] is False
    assert told["meet"] == "http.py" and told["meet_kind"] == "callee"


def test_asking_AGAINST_the_flow_is_re_presented_in_call_order(chain: Path) -> None:
    """Asked scoring → narrator, but every call runs the other way. The route
    is the same three files; the presentation descends the call stack, and the
    flip is declared rather than done silently."""
    told = story(chain, "scoring.py", "narrator.py")
    assert told["flipped"] is True
    assert [hop["file"] for hop in told["hops"]] == [  # type: ignore[index]
        "narrator.py", "agents.py", "scoring.py"]


def test_asking_WITH_the_flow_is_left_exactly_as_asked(chain: Path) -> None:
    """The user's framing is respected when it is not wrong. Flipping a route
    that already reads correctly is just disrespecting the question."""
    told = story(chain, "narrator.py", "scoring.py")
    assert told["flipped"] is False


def test_a_MIXED_route_is_never_flipped(meeting: Path) -> None:
    """A meeting is not a chain in either direction, so there is no call order
    to restore — flipping it would trade one wrong story for another."""
    with Store(meeting) as store:
        hops = [{"file": "scoring.py", "via": ""}, {"file": "http.py", "via": "import"},
                {"file": "rerank.py", "via": "import"}]
        flipped_hops, flipped = orient_hops(store, hops)
    assert flipped is False and flipped_hops == hops


def test_every_hop_after_the_first_carries_its_symbols_and_code(chain: Path) -> None:
    told = story(chain, "narrator.py", "scoring.py")
    hops = told["hops"]
    assert isinstance(hops, list)
    assert hops[1]["symbols"] == ["dispatch"]
    assert (hops[1]["code"] or {})["symbol"] == "dispatch"
    assert hops[2]["symbols"] == ["fuse"]


def test_the_first_hop_carries_no_evidence_because_it_crossed_nothing(
        chain: Path) -> None:
    told = story(chain, "narrator.py", "scoring.py")
    first = told["hops"][0]              # type: ignore[index]
    assert first["via"] == "" and "code" not in first


def test_a_one_file_route_is_told_without_inventing_a_hop(chain: Path) -> None:
    with Store(chain) as store:
        told = tell(store, chain, [{"file": "narrator.py", "via": ""}])
    assert told["chain"] is True and len(told["hops"]) == 1  # type: ignore[arg-type]


def test_an_empty_route_tells_nothing(chain: Path) -> None:
    with Store(chain) as store:
        told = tell(store, chain, [])
    assert told["hops"] == [] and told["chain"] is True and told["meet"] is None
