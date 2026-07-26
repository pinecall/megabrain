"""The narrator keeps reading until it stops asking for files.

Retrieval is where an answer starts, not all of it: the span that matters can
sit fifty lines below the chunk that matched, and a walkthrough of a big ugly
repository needs the file rather than the excerpt. So the model gets `open_file`
and this loop feeds it, bounded by MAX_ROUNDS and fail-open on a backend that
does not know tools.

Driven by a fake provider on purpose. The loop's contract is "ask, serve, ask
again, stop" — a property of the code, not of any model's willingness to use a
tool on a given day.
"""

from __future__ import annotations

from typing import Any

from megabrain.ask._converse import MAX_ROUNDS, converse
from megabrain.ask.events import emit_nothing
from megabrain.chunkers.model import Chunk
from megabrain.providers.chat import Answer, ToolCall
from megabrain.storage import Store


class Fake:
    """A provider that asks for files, then answers."""

    model = "fake"

    def __init__(self, *turns: Answer) -> None:
        self.turns, self.bodies = list(turns), []

    def stream_chat(self, body: dict[str, Any], on_delta: Any = None) -> Answer:
        self.bodies.append(body)
        return self.turns[min(len(self.bodies) - 1, len(self.turns) - 1)]


def call(path: str, ident: str = "1") -> ToolCall:
    return ToolCall(id=ident, name="open_file", arguments=f'{{"path": "{path}"}}')


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    store.files.upsert("lib/app.rb", "sha", "", None)
    store.chunks.insert([Chunk(file="lib/app.rb", kind="class", name="App", part=None,
                               start_line=1, end_line=2, text="class App\nend",
                               breadcrumb="lib/app.rb")], None)
    return store


def test_the_file_the_model_ASKS_for_comes_back(tmp_path) -> None:
    """The whole point: it asked, so it reads — verbatim from the index."""
    provider = Fake(Answer(text="", tool_calls=[call("lib/app.rb")]),
                    Answer(text="here is the flow"))
    with repo(tmp_path) as store:
        answer = converse(provider, "explain it", store, emit=emit_nothing)
    assert answer.text == "here is the flow"
    served = provider.bodies[1]["messages"][-1]
    assert served["role"] == "tool" and "class App" in served["content"]


def test_the_tool_is_OFFERED_on_every_turn(tmp_path) -> None:
    """A model that cannot see the tool cannot use it, and this loop is the only
    place that puts it on the wire."""
    provider = Fake(Answer(text="done"))
    with repo(tmp_path) as store:
        converse(provider, "explain it", store, emit=emit_nothing)
    body = provider.bodies[0]
    assert [t["function"]["name"] for t in body["tools"]] == ["open_file"]
    assert body["parallel_tool_calls"] is True, "one file per turn is a round trip each"


def test_a_model_that_never_stops_is_STOPPED(tmp_path) -> None:
    """Bounded: a model that keeps browsing would otherwise spend the caller's
    afternoon one file at a time."""
    provider = Fake(Answer(text="", tool_calls=[call("lib/app.rb")]))
    with repo(tmp_path) as store:
        converse(provider, "explain it", store, emit=emit_nothing)
    assert len(provider.bodies) == MAX_ROUNDS


def test_a_backend_with_NO_tool_support_still_answers(tmp_path) -> None:
    """Fail-open. An answer with no tool calls is the answer."""
    provider = Fake(Answer(text="the flow, without opening anything"))
    with repo(tmp_path) as store:
        answer = converse(provider, "explain it", store, emit=emit_nothing)
    assert answer.text == "the flow, without opening anything"
    assert len(provider.bodies) == 1


def test_every_open_is_ANNOUNCED(tmp_path) -> None:
    """The caller can see what was read. Without the event a walkthrough that
    silently opened six files is indistinguishable from one that opened none."""
    provider = Fake(Answer(text="", tool_calls=[call("lib/app.rb")]),
                    Answer(text="done"))
    seen: list[dict[str, Any]] = []
    with repo(tmp_path) as store:
        converse(provider, "explain it", store, emit=seen.append)
    assert [e["file"] for e in seen if e["type"] == "opened"] == ["lib/app.rb"]
