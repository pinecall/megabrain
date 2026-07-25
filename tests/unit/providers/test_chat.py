"""The chat backends: one Protocol, N implementations, resolved by a registry.

Everything here is offline. A chat test that needs a key is testing somebody's
endpoint, not this code.
"""

from __future__ import annotations

import json

import pytest

from megabrain._errors import ProviderError
from megabrain.providers.chat import ChatProvider, resolve
from megabrain.providers.chat.openai_compat import OpenAICompatible
from tests.unit.providers.fake import FakeTransport, ok, status

pytestmark = pytest.mark.usefixtures("no_sleep")


def sse(*events: object) -> bytes:
    """An OpenAI-compatible stream, terminated the way a real one is."""
    lines = [f"data: {json.dumps(event)}" for event in events]
    return ("\n".join([*lines, "data: [DONE]", ""])).encode()


def delta(content: str = "", finish: str = "", **extra: object) -> dict[str, object]:
    return {"choices": [{"delta": {"content": content, **extra},
                         "finish_reason": finish or None}]}


def _provider(*responses: object) -> tuple[OpenAICompatible, FakeTransport]:
    transport = FakeTransport(list(responses))  # type: ignore[arg-type]
    return OpenAICompatible(transport=transport, api_key="k"), transport


def test_the_deltas_are_concatenated_in_order() -> None:
    provider, _ = _provider(ok(sse(delta("Hello"), delta(" world"), delta(finish="stop"))))
    answer = provider.stream_chat({"model": "m", "messages": []})
    assert answer.text == "Hello world"
    assert answer.finish_reason == "stop"


def test_each_delta_reaches_the_caller_as_it_arrives() -> None:
    """The whole reason for streaming: a reader watching a long answer appear
    is not waiting, and one that arrives whole after 40 seconds is."""
    provider, _ = _provider(ok(sse(delta("a"), delta("b"), delta("c"))))
    seen: list[str] = []
    provider.stream_chat({"model": "m", "messages": []}, on_delta=seen.append)
    assert seen == ["a", "b", "c"]


def test_keep_alive_comments_are_skipped() -> None:
    """Providers send `: ping` to hold the connection open. Parsed as data it
    is a JSON error, and a stream that dies on a keep-alive dies at random."""
    raw = b": ping\n\ndata: " + json.dumps(delta("hi")).encode() + b"\n\ndata: [DONE]\n"
    provider, _ = _provider(ok(raw))
    assert provider.stream_chat({"model": "m", "messages": []}).text == "hi"


def test_fragmented_tool_calls_accumulate_per_index() -> None:
    """A tool call arrives in pieces — the name in one frame, the arguments
    across several. Anything that does not accumulate gets `{"pa` as JSON."""
    provider, _ = _provider(ok(sse(
        delta(tool_calls=[{"index": 0, "id": "c1",
                           "function": {"name": "read", "arguments": '{"pa'}}]),
        delta(tool_calls=[{"index": 0, "function": {"arguments": 'th":"a.py"}'}}]),
        delta(finish="tool_calls"))))
    calls = provider.stream_chat({"model": "m", "messages": []}).tool_calls
    assert len(calls) == 1
    assert calls[0].name == "read"
    assert json.loads(calls[0].arguments) == {"path": "a.py"}


def test_two_tool_calls_keep_their_order() -> None:
    provider, _ = _provider(ok(sse(
        delta(tool_calls=[{"index": 1, "id": "b", "function": {"name": "second"}}]),
        delta(tool_calls=[{"index": 0, "id": "a", "function": {"name": "first"}}]))))
    assert [c.name for c in provider.stream_chat({"model": "m", "messages": []}).tool_calls] \
        == ["first", "second"]


def test_a_mid_stream_error_frame_is_raised_not_returned_as_text() -> None:
    """Providers report a failure INSIDE a 200 stream. Treated as content it
    becomes part of the answer, which is how a provider outage ends up quoted
    to the user as if the model had said it."""
    provider, _ = _provider(ok(sse({"error": {"message": "upstream is down"}})))
    with pytest.raises(ProviderError, match="upstream is down"):
        provider.stream_chat({"model": "m", "messages": []})


def test_a_transport_failure_retries() -> None:
    provider, transport = _provider(status(503), ok(sse(delta("recovered"))))
    assert provider.stream_chat({"model": "m", "messages": []}).text == "recovered"
    assert transport.calls == 2


def test_it_stops_retrying_once_the_caller_has_SEEN_output() -> None:
    """Retrying after deltas were delivered prints the answer twice — the
    terminal shows half a sentence, then the whole sentence again."""
    broken = b"data: " + json.dumps(delta("half an ans")).encode() + b"\n"
    provider, transport = _provider(ok(broken), ok(sse(delta("whole answer"))))
    seen: list[str] = []
    answer = provider.stream_chat({"model": "m", "messages": []}, on_delta=seen.append)
    assert seen == ["half an ans"]
    assert answer.text == "half an ans"
    assert transport.calls == 1, "it retried after the caller had already seen output"


def test_the_request_carries_the_model_and_asks_for_a_stream() -> None:
    provider, transport = _provider(ok(sse(delta("x"))))
    provider.stream_chat({"model": "some-model", "messages": [{"role": "user"}]})
    body = json.loads(transport.sent[0].body)
    assert body["model"] == "some-model" and body["stream"] is True


def test_chat_text_returns_just_the_answer() -> None:
    provider, _ = _provider(ok(sse(delta("42"), delta(finish="stop"))))
    assert provider.chat_text("m", "what is six times seven?") == "42"


# ---- the registry -----------------------------------------------------------


def test_a_provider_that_is_not_configured_is_not_resolved() -> None:
    """`available()` is a cheap self-gate, so a backend nobody set up is
    skipped instead of failing at the first call."""
    class Absent:
        name = "absent"
        agent_stream = None

        def available(self) -> bool:
            return False

    assert resolve([Absent()]) is None                     # type: ignore[list-item]


def test_the_first_available_provider_wins() -> None:
    class Ready:
        name = "ready"
        agent_stream = None

        def available(self) -> bool:
            return True

    chosen = resolve([Ready(), Ready()])                   # type: ignore[list-item]
    assert chosen is not None and chosen.name == "ready"


def test_the_openai_backend_satisfies_the_protocol_structurally() -> None:
    """No base class to inherit: an adapter with the right shape IS a
    provider, which is what lets a caller add one without importing us."""
    assert isinstance(OpenAICompatible(api_key="k"), ChatProvider)


def test_the_deltas_arrive_BEFORE_the_stream_ends() -> None:
    """The claim streaming makes, tested rather than assumed.

    The transport yields one line at a time from a generator, so a callback
    that fires while lines remain unread proves incremental delivery. A client
    that buffered the whole body would still pass every other test in this
    file and stream nothing.
    """
    remaining: list[str] = []
    raw = sse(delta("first"), delta("second"), delta("third"))

    class Watching(FakeTransport):
        def open(self, url, body, headers, timeout):  # type: ignore[no-untyped-def]
            opened = super().open(url, body, headers, timeout)
            lines = list(opened.lines)

            def counted():  # type: ignore[no-untyped-def]
                for index, line in enumerate(lines):
                    remaining.append(f"{len(lines) - index - 1} lines left")
                    yield line
            return type(opened)(status=opened.status, lines=counted(),
                                headers=opened.headers)

    provider = OpenAICompatible(transport=Watching([ok(raw)]), api_key="k")
    seen_at: list[str] = []
    provider.stream_chat({"model": "m", "messages": []},
                         on_delta=lambda _text: seen_at.append(remaining[-1]))

    assert seen_at, "no delta was delivered at all"
    assert any("0 lines left" != moment for moment in seen_at), \
        "every delta arrived only after the stream was fully read"
