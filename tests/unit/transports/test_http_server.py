"""The wire: a real socket, a real client, real SSE frames.

Everything the route tests deliberately skip lives here — status lines, JSON
bodies, the auth gate, chunked event streams. Once, end to end, because these
are exactly the parts that look fine in a unit test and fail in a browser.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest

from megabrain.transports.http.app import build_server
from megabrain.transports.http.security import Policy
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("megabrain.retrieval.state.Embedder", CountingEmbedder)
    monkeypatch.setattr("megabrain.indexing.indexer._default_embedder", CountingEmbedder)


class Client:
    """A tiny HTTP client over the real port the server bound."""

    def __init__(self, port: int, token: str = "") -> None:
        self.port, self.token = port, token

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        auth = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return {**auth, **(extra or {})}

    def get(self, path: str) -> tuple[int, Any]:
        return self._send("GET", path, None)

    def post(self, path: str, body: object = None) -> tuple[int, Any]:
        return self._send("POST", path, body)

    def _send(self, method: str, path: str, body: object) -> tuple[int, Any]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=30)
        payload = json.dumps(body or {}).encode()
        connection.request(method, path, payload,
                           self._headers({"Content-Type": "application/json"}))
        response = connection.getresponse()
        raw = response.read().decode()
        connection.close()
        try:
            return response.status, json.loads(raw)
        except ValueError:
            return response.status, raw

    def events(self, path: str, body: object) -> list[tuple[str, Any]]:
        """Read an SSE response to completion, returning (event, data)."""
        connection = HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.request("POST", path, json.dumps(body).encode(),
                           self._headers({"Content-Type": "application/json"}))
        response = connection.getresponse()
        assert response.status == 200, response.read()
        assert response.getheader("Content-Type") == "text/event-stream"
        frames = _parse(response.read().decode())
        connection.close()
        return frames


def _parse(raw: str) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for block in raw.split("\n\n"):
        name, data = "", ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if name and data:
            out.append((name, json.loads(data)))
    return out


def _serve(policy: Policy | None = None) -> Iterator[Client]:
    server = build_server("127.0.0.1", 0, policy)      # port 0: the OS picks a free one
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield Client(server.server_address[1], policy.token if policy else "")
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def client() -> Iterator[Client]:
    yield from _serve()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return write(tmp_path, {"svc.py": "import util\n\n\ndef handle(request):\n"
                                      "    return util.run(request)\n",
                            "util.py": "def run(request):\n    return request\n"})


def test_a_real_request_gets_a_real_json_response(client: Client) -> None:
    status, body = client.get("/health")
    assert status == 200 and body["ok"] is True


def test_a_trailing_slash_is_the_same_route(client: Client) -> None:
    assert client.get("/health/")[0] == 200


def test_a_malformed_body_is_400_not_a_crash(client: Client) -> None:
    connection = HTTPConnection("127.0.0.1", client.port, timeout=10)
    connection.request("POST", "/search", b"{not json",
                       {"Content-Type": "application/json"})
    assert connection.getresponse().status == 400
    connection.close()


def test_indexing_streams_progress_then_a_report(repo: Path, client: Client) -> None:
    """The one operation that takes minutes. A response that arrives only at
    the end gives a browser nothing to show, and a large repository becomes
    indistinguishable from a hung server."""
    frames = client.events("/index/stream", {"path": str(repo)})
    kinds = [name for name, _ in frames]

    assert "progress" in kinds, "no progress was streamed"
    assert kinds[-1] == "done", kinds[-3:]
    assert frames[-1][1]["files"] == 2
    assert frames[-1][1]["edges"] > 0


def test_a_failing_index_streams_an_error_frame_rather_than_stopping(
        tmp_path: Path, client: Client) -> None:
    """A stream that just stops is indistinguishable from a dropped
    connection, and the browser retries it."""
    frames = client.events("/index/stream", {"path": str(tmp_path / "does-not-exist")})
    assert frames[-1][0] == "error", frames[-1]


def test_without_a_token_every_route_is_open() -> None:
    for client in _serve():
        assert client.get("/repos")[0] == 200
        break


def test_with_a_token_the_data_routes_demand_it() -> None:
    for authed in _serve(Policy(token="s3cret")):
        assert authed.get("/repos")[0] == 200            # correct token
        anonymous = Client(authed.port)
        assert anonymous.get("/repos")[0] == 401
        assert anonymous.get("/health")[0] == 200, "health must stay reachable"
        assert anonymous.get("/config")[0] == 200, "config must stay reachable"
        break


def test_a_readonly_server_refuses_to_index() -> None:
    for client in _serve(Policy(readonly=True)):
        status, body = client.post("/index/stream", {"path": "."})
        assert status == 403 and body["code"] == "error"
        break


def test_the_rate_limit_answers_429_when_exceeded() -> None:
    for client in _serve(Policy(rate_limit=2)):
        codes = [client.get("/repos")[0] for _ in range(4)]
        assert codes[:2] == [200, 200]
        assert codes[2:] == [429, 429]
        break


def test_binding_beyond_localhost_without_a_token_is_refused() -> None:
    """Indexing reads any path the process can reach. An open bind on a shared
    network is not a warning — it is a mistake with a blast radius."""
    with pytest.raises(ValueError, match="without a token"):
        build_server("0.0.0.0", 0)


def test_binding_beyond_localhost_WITH_a_token_is_allowed() -> None:
    server = build_server("0.0.0.0", 0, Policy(token="s3cret"))
    server.server_close()
