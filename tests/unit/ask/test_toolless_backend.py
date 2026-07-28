"""A backend that REJECTS the tools field still narrates.

`converse` documents the fail-open — "a backend with no tool support returns its
text on the first pass" — and until this test it only held for a backend that
ACCEPTED the field and returned no calls. One that refuses the request outright
took the whole walkthrough down with it.

MEASURED against Ollama: `gemma3:1b` answers a plain chat request and returns
HTTP 400 `does not support tools` the moment the narrator's `open_file` is
attached. Every local model without tool support behaves this way, which is what
made "fully local" look like it had been lost in the migration.
"""

from __future__ import annotations

from typing import Any

import pytest

from megabrain._provider_errors import ProviderError
from megabrain.ask.converse.loop import converse
from megabrain.chunkers.model import Chunk
from megabrain.providers.chat import Answer
from megabrain.storage import Store


def repo(tmp_path: Any) -> Store:
    store = Store(tmp_path)
    store.files.upsert("app/auth.py", "sha", "", None)
    store.chunks.insert([Chunk(file="app/auth.py", kind="function", part=None,
                               name="verify_token", start_line=1, end_line=2,
                               text="def verify_token(token):\n    ...",
                               breadcrumb="app/auth.py")], None)
    return store


class ToollessBackend:
    """Refuses any body carrying `tools`, the way a local runtime does."""

    name = "toolless"
    model = "gemma3:1b"
    agent_stream = None

    def __init__(self, message: str = "does not support tools") -> None:
        self.message = message
        self.bodies: list[dict[str, Any]] = []

    def available(self) -> bool:
        return True

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        return ""

    def stream_chat(self, body: dict[str, Any], *,
                    on_delta: Any = None) -> Answer:
        self.bodies.append(body)
        if body.get("tools"):
            raise ProviderError(
                f"http://localhost:11434/v1/chat/completions failed with "
                f"HTTP 400: {self.message}", status=400)
        return Answer(text="verify_token checks the Bearer prefix, then looks "
                           "the raw token up in SESSIONS.")


def test_a_backend_that_refuses_tools_still_answers(tmp_path: Any) -> None:
    provider = ToollessBackend()
    with repo(tmp_path) as store:
        answer = converse(provider, "how does token verification work?", store,
                          emit=lambda _event: None)
    assert "verify_token" in answer.text


def test_the_retry_drops_the_tools_and_keeps_everything_else(tmp_path: Any) -> None:
    """Dropped, not emptied: `tools: []` is still the field, and the runtimes
    that reject it reject the empty list too."""
    provider = ToollessBackend()
    with repo(tmp_path) as store:
        converse(provider, "q", store, emit=lambda _event: None)
    first, second = provider.bodies[0], provider.bodies[1]
    assert first["tools"] and "tools" not in second
    assert "parallel_tool_calls" not in second
    assert second["max_tokens"] == first["max_tokens"]
    assert second["messages"] == first["messages"]


def test_the_fallback_is_announced(tmp_path: Any) -> None:
    """Silence here would be the worst outcome: the walkthrough quietly loses
    the ability to open files and nothing says the lane changed."""
    seen: list[dict[str, Any]] = []
    with repo(tmp_path) as store:
        converse(ToollessBackend(), "q", store, emit=seen.append)
    assert any(event["type"] == "toolless" for event in seen)


def test_a_real_failure_is_NOT_swallowed_as_a_tool_problem(tmp_path: Any) -> None:
    """The retry must be narrow. A 500, a bad key or a dead endpoint has to
    keep failing — retrying those without tools buys a second outage and
    reports it as if tool support were the issue."""
    provider = ToollessBackend(message="upstream is on fire")
    with repo(tmp_path) as store, pytest.raises(ProviderError,
                                                match="upstream is on fire"):
        converse(provider, "q", store, emit=lambda _event: None)


def test_the_toolless_retry_happens_once_not_every_round(tmp_path: Any) -> None:
    provider = ToollessBackend()
    with repo(tmp_path) as store:
        converse(provider, "q", store, emit=lambda _event: None)
    assert len(provider.bodies) == 2
