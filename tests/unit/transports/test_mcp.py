"""The MCP surface: five tools, one dispatch, JSON-RPC over stdio.

Driven the way a host drives it — a JSON-RPC message in, a response object out
— because the protocol handling IS the surface. Calling the use cases directly
would test the engine again and leave the transport untested, which is the
half that breaks when a tool gains a parameter.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from megabrain.transports.mcp.protocol import PROTOCOL, respond
from megabrain.transports.mcp.schema import json_schema
from megabrain.transports.mcp.server import serve
from megabrain.transports.mcp.tools import TOOLS, listing
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No network in a transport test — patched at the seam `load_state` uses."""
    monkeypatch.setattr("megabrain.retrieval.state.Embedder", CountingEmbedder)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"svc.py": "import util\n\n\nclass Service:\n"
                               "    def handle(self, request):\n"
                               '        """Answer one request."""\n'
                               "        return util.run(request)\n",
                     "util.py": "def run(request):\n    return request\n"})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def _call(name: str, **arguments: Any) -> dict[str, Any]:
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
    reply = respond(message)
    assert reply is not None
    return reply["result"]


def _text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


# ── the surface ──────────────────────────────────────────────────────────

def test_the_agent_sees_exactly_the_three_tools() -> None:
    """Every tool costs the calling agent context and a routing decision, so
    the surface stays the shortest one that closes the loop: narrate a mechanism
    from the whole repository (`ask`), map it (`search`), and make a repository
    answerable at all (`index`).

    It was briefly five. `megabrain_code` and `megabrain_replace` were measured
    across five tasks in three languages and REMOVED: what carried the value was
    the narrator opening files until it had the whole flow, and that now belongs
    to `ask`. The edit machinery around it kept being discarded by the readers it
    was built for — a prepared batch was wrong both times it was measured — and
    applying an edit is work the host's own editor already does.
    """
    assert {tool.name for tool in TOOLS} == {
        "megabrain_ask", "megabrain_search", "megabrain_index"}


def test_every_schema_is_generated_from_its_contract() -> None:
    """One definition, not two. A parameter added to the TypedDict in
    `contracts/` reaches the wire without anyone editing a JSON literal."""
    for tool in TOOLS:
        schema = json_schema(tool.params)
        assert set(schema["required"]) == set(tool.params.__required_keys__)
        assert set(schema["properties"]) == (
            set(tool.params.__required_keys__) | set(tool.params.__optional_keys__))


def test_no_parameter_ships_undocumented() -> None:
    """A schema field with no description is a field the agent guesses at."""
    for tool in TOOLS:
        for name, prop in json_schema(tool.params)["properties"].items():
            assert prop.get("description"), f"{tool.name}.{name} has no description"


def test_a_literal_becomes_an_enum() -> None:
    """`content: Content` is L0's Literal["code", "docs"]. If it rendered as a
    bare string the agent could send anything and only find out at dispatch."""
    prop = json_schema(TOOLS[0].params)["properties"]
    content = next(p for name, p in prop.items() if name == "content")
    assert content["enum"] == ["code", "docs"]


def test_listing_is_what_tools_list_returns() -> None:
    reply = respond({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert reply is not None
    assert reply["result"]["tools"] == listing()
    assert {t["name"] for t in listing()} == {tool.name for tool in TOOLS}


def test_initialize_hands_over_the_instructions() -> None:
    """The only megabrain text an agent is guaranteed to see: with tool search
    on, the schemas stay deferred until it goes looking for them."""
    reply = respond({"jsonrpc": "2.0", "id": 3, "method": "initialize"})
    assert reply is not None
    result = reply["result"]
    assert result["protocolVersion"] == PROTOCOL
    assert "megabrain_search" in result["instructions"]
    assert result["serverInfo"]["name"] == "megabrain"


def test_a_notification_gets_no_response() -> None:
    """A message without an id is a notification. Answering one is a protocol
    violation that some hosts treat as a dead server."""
    assert respond({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


# ── the three verbs ──────────────────────────────────────────────────────

def test_search_returns_a_MAP_by_default(repo: Path) -> None:
    """The default is the map, not the bodies. Measured on a real bundle: the
    map costs ~2 700 tokens where CORE-with-bodies costs ~8 100, and it still
    names the file, the best span and the symbols — which is what an agent needs
    to decide where to look. The code is one `bodies: true` away.
    """
    text = _text(_call("megabrain_search", repo_path=str(repo),
                       task="how does Service handle a request"))
    assert "## CORE" in text and "svc.py" in text
    assert "```" not in text, "the default rendered code bodies"


def test_search_WITH_bodies_inlines_the_code(repo: Path) -> None:
    """Opt-in, and when asked for it must really carry the code — an agent that
    passes `bodies: true` is choosing to read here instead of opening files."""
    text = _text(_call("megabrain_search", repo_path=str(repo),
                       task="how does Service handle a request", bodies=True))
    assert "def handle" in text and "```" in text


def test_search_scope_reaches_the_engine(repo: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """scope_path EXCLUDES everything outside it from retrieval — if it stopped
    at the transport the answer would silently widen back to the whole repo."""
    seen: dict[str, object] = {}

    def spy(_start: object, query: str, **kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {"query": query, "repo": "r", "tier1": [], "tier2": [],
                "anchors": [], "flows": [], "ms": 1}

    monkeypatch.setattr("megabrain.transports.mcp.dispatch.search", spy)
    _call("megabrain_search", repo_path=str(repo), task="anything",
          scope_path="src", content="docs")
    assert seen["path_filter"] == "src"
    assert seen["content"] == "docs"


def test_ask_is_buffered_and_never_streams(repo: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP is request/response: the consuming agent reads the final text only,
    so a partial stream would be a half-written walkthrough with no way back."""
    seen: dict[str, object] = {}

    def spy(_start: object, question: str, **kwargs: object) -> str:
        seen.update(kwargs)
        return f"walkthrough of {question}"

    monkeypatch.setattr("megabrain.transports.mcp.dispatch.ask", spy)
    text = _text(_call("megabrain_ask", repo_path=str(repo),
                       question="how does it handle a request"))
    assert text == "walkthrough of how does it handle a request"
    assert seen["content"] == "code", "ask defaults to code, like the use case"
    assert "emit" not in seen, "the MCP transport must not subscribe to events"


def test_ask_narrates_the_prose_when_asked(repo: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def spy(_start: object, _question: str, **kwargs: object) -> str:
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr("megabrain.transports.mcp.dispatch.ask", spy)
    _call("megabrain_ask", repo_path=str(repo), question="q", content="docs")
    assert seen["content"] == "docs"


def test_a_missing_required_argument_is_an_error_not_a_crash(repo: Path) -> None:
    """A KeyError three frames down reaches the host as a dead tool call."""
    result = _call("megabrain_search", repo_path=str(repo))
    assert result["isError"] is True
    assert "task" in _text(result)


def test_an_unknown_tool_says_which_ones_exist() -> None:
    result = _call("megabrain_explain", repo_path=".")
    assert result["isError"] is True
    assert "megabrain_ask" in _text(result)


def test_every_advertised_tool_dispatches(repo: Path) -> None:
    """Anti-vacuum: a tool in the listing that dispatch does not know is a
    surface the agent can see and never use."""
    for tool in TOOLS:
        arguments = {key: str(repo) if key == "repo_path" else "handle"
                     for key in tool.params.__required_keys__}
        result = _call(tool.name, **arguments)
        assert "unknown tool" not in _text(result).lower()


# ── the stdio loop ───────────────────────────────────────────────────────

def test_serve_answers_line_by_line_and_skips_junk() -> None:
    """One JSON object per line, one response per line. A malformed line is
    skipped rather than fatal: a host that writes garbage once should not take
    the server down for the rest of the session."""
    import io

    stdin = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
                        "not json\n"
                        "\n"
                        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
                        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n')
    stdout = io.StringIO()
    serve(stdin, stdout)
    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [r["id"] for r in replies] == [1, 2]


def test_listing_the_tools_does_not_load_numpy() -> None:
    """A host starts this server and lists tools before asking anything. That
    handshake must not pay for numpy, tree_sitter or a sqlite connection."""
    code = ("import sys;"
            "from megabrain.transports.mcp.protocol import respond;"
            "respond({'id': 1, 'method': 'tools/list'});"
            "print('numpy' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=ROOT, check=True)
    assert out.stdout.strip() == "False"
