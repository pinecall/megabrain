"""A scripted stand-in for `claude_agent_sdk`.

The SDK's seam is an IMPORT, not a socket, so the fake has to be a module-shaped
object rather than a transport. It records the prompt and the options every call
received, which is how a test asserts the translation was right — the equivalent
of `FakeTransport.sent`.

Messages are duck-typed by CLASS NAME, exactly as the provider dispatches them:
the real SDK ships dataclasses this suite must never import, and naming a local
class `StreamEvent` is what lets the whole provider be tested with no
`claude-agent-sdk` installed anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class StreamEvent:
    event: dict[str, Any]


@dataclass
class AssistantMessage:
    content: list[Any] = field(default_factory=list)


@dataclass
class TextBlock:
    text: str


@dataclass
class ResultMessage:
    """The CLI's own verdict on the run. `subtype` is NOT the error.

    Observed against claude-agent-sdk 0.2.128: a refused run arrives as
    subtype='success', is_error=True, result='Credit balance is too low' — and
    the SDK then raises carrying the SUBTYPE, so the only actionable sentence
    in the exchange is the one in `result`.
    """

    subtype: str = "success"
    is_error: bool = False
    result: str = ""


@dataclass
class Options:
    """What `ClaudeAgentOptions` was asked for, kept verbatim for assertions."""

    kwargs: dict[str, Any]


def delta(text: str) -> StreamEvent:
    return StreamEvent({"type": "content_block_delta", "delta": {"text": text}})


def capped() -> StreamEvent:
    return StreamEvent({"type": "message_delta", "delta": {"stop_reason": "max_tokens"}})


def ping() -> StreamEvent:
    """An event the provider must ignore rather than parse as text."""
    return StreamEvent({"type": "content_block_start", "index": 0})


class FakeSDK:
    """Replays `script` for every `query()`. An Exception entry is raised."""

    def __init__(self, script: list[Any] | None = None,
                 error: Exception | None = None) -> None:
        self.script = script or []
        self.error = error
        self.prompts: list[str] = []
        self.options: list[Options] = []

    def ClaudeAgentOptions(self, **kwargs: Any) -> Options:  # noqa: N802
        return Options(kwargs)

    def query(self, *, prompt: str, options: Any) -> AsyncIterator[Any]:
        self.prompts.append(prompt)
        self.options.append(options)
        return self._stream()

    async def _stream(self) -> AsyncIterator[Any]:
        if self.error is not None:
            raise self.error
        for message in self.script:
            yield message


class HangingSDK(FakeSDK):
    """Never yields. Pins that a stalled CLI is bounded, not waited on."""

    async def _stream(self) -> AsyncIterator[Any]:
        import asyncio

        await asyncio.sleep(3600)
        yield None      # pragma: no cover - unreachable, keeps this a generator
