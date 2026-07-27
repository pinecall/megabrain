"""The routes as what they are: functions from a Request to a Reply.

No socket here. The wire is tested once, end to end, in test_http_server.py —
paying for a live port in every route test buys nothing and costs seconds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.storage import Store
from megabrain.transports.http.messages import Request
from megabrain.transports.http.router import dispatch
from megabrain.transports.http.security import Policy
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("megabrain.search.state.Embedder", CountingEmbedder)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"svc.py": "import util\n\n\nclass Service:\n"
                               "    def handle(self, request):\n"
                               "        return util.run(request)\n",
                     "util.py": "def run(request):\n    return request\n"})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def _get(path: str, **query: str) -> Request:
    return Request(method="GET", path=path, query=query)


def _post(path: str, **body: object) -> Request:
    return Request(method="POST", path=path, body=body)


def test_health_without_a_repo_is_just_liveness() -> None:
    reply = dispatch(_get("/health"))
    assert reply.status == 200
    assert reply.payload["ok"] is True                        # type: ignore[index]


def test_health_reports_an_EMPTY_index_as_not_ok(tmp_path: Path) -> None:
    """"The server is up" is not the question anyone is asking: an empty index
    answers every query with nothing and looks healthy from outside.

    Built through the store rather than through `build_index`, which now refuses
    to produce one — an index of nothing is a failure, not a state. It can still
    EXIST (an interrupted run, an older build), so health still has to say so.
    """
    with Store(tmp_path):
        pass                                                  # an index, no files
    reply = dispatch(_get("/health", repo=str(tmp_path)))
    assert reply.payload["ok"] is False                       # type: ignore[index]
    assert reply.payload["chunks"] == 0                       # type: ignore[index]


def test_health_on_a_path_with_no_index_is_404_not_500(tmp_path: Path) -> None:
    reply = dispatch(_get("/health", repo=str(tmp_path / "nowhere")))
    assert reply.status == 404
    assert reply.payload["code"] == "index_not_found"         # type: ignore[index]


def test_config_never_leaks_the_token() -> None:
    """It is readable BEFORE authenticating — that is the point of it — so it
    may say a token is required and nothing more."""
    request = Request(method="GET", path="/config",
                      policy=Policy(token="s3cret", readonly=True, rate_limit=30))
    payload = dispatch(request).payload
    assert payload["auth"] is True and payload["readonly"] is True   # type: ignore[index]
    assert "s3cret" not in str(payload)


def test_repos_lists_what_was_indexed(repo: Path) -> None:
    entries = dispatch(_get("/repos")).payload["repos"]        # type: ignore[index]
    assert [e["path"] for e in entries] == [str(repo)]
    assert entries[0]["chunks"] > 0, "counts are read live from the index"


def test_search_returns_the_bundle_contract(repo: Path) -> None:
    reply = dispatch(_post("/search", query="how does Service handle", repo=str(repo)))
    assert reply.status == 200
    assert {"query", "repo", "tier1", "tier2", "ms"} <= set(reply.payload)  # type: ignore[arg-type]


def test_search_without_a_query_is_400(repo: Path) -> None:
    assert dispatch(_post("/search", query="   ", repo=str(repo))).status == 400


def test_search_on_an_unindexed_path_carries_the_engine_code(tmp_path: Path) -> None:
    """The taxonomy already knows its own status and code, so no route
    invents an HTTP status of its own."""
    reply = dispatch(_post("/search", query="anything", repo=str(tmp_path / "x")))
    assert reply.status == 404
    assert reply.payload["code"] == "index_not_found"          # type: ignore[index]


def test_get_returns_one_symbol(repo: Path) -> None:
    reply = dispatch(_get("/get", file="svc.py", symbol="handle", repo=str(repo)))
    assert "def handle" in reply.payload["text"]               # type: ignore[index]


def test_get_of_an_unknown_symbol_is_404(repo: Path) -> None:
    reply = dispatch(_get("/get", file="svc.py", symbol="nope", repo=str(repo)))
    assert reply.status == 404
    assert reply.payload["code"] == "no_such_symbol"           # type: ignore[index]


def test_symbols_returns_the_outline_without_the_source(repo: Path) -> None:
    """A file tree draws one of these per visible file; shipping every file's
    source to render a sidebar is the difference between a click and a wait."""
    payload = dispatch(_get("/symbols", file="svc.py", repo=str(repo))).payload
    assert "text" not in payload                               # type: ignore[operator]
    assert any(s["name"].endswith("handle") for s in payload["symbols"])  # type: ignore[index]


def test_a_known_path_under_the_wrong_method_is_405() -> None:
    """405 and 404 send a caller to completely different places."""
    reply = dispatch(Request(method="GET", path="/search"))
    assert reply.status == 405
    assert "POST" in reply.payload["error"]                    # type: ignore[index]


def test_an_unknown_path_is_404() -> None:
    assert dispatch(_get("/nope")).status == 404
