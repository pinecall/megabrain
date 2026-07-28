"""What comes OUT of one SDK run: the message stream, read as an `Answer`.

Its own module for the same reason `_frames.py` is: every trap here fails
silently. A whole-block message counted alongside the deltas it repeats returns
the answer twice; an event that carries no text parses to an empty string that
looks exactly like a finished stream; a stop reason left in the SDK's own
vocabulary means a truncated answer never looks truncated.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, cast

from ..._provider_errors import ProviderError
from .base import Answer, OnDelta

__all__ = ["drain"]


async def drain(stream: AsyncIterator[Any], on_delta: OnDelta | None) -> Answer:
    """One SDK run, consumed to the end, as one `Answer`.

    Drained fully on purpose: an abandoned async generator leaves the CLI
    subprocess and its pipes alive.

    Dispatch is on the CLASS NAME, not `isinstance`. The SDK's message types are
    an optional import, and a check that needed them would make this module
    unimportable exactly where it has to stay testable.
    """
    parts: list[str] = []
    streamed = False
    finish = ""
    async for message in stream:
        kind = type(message).__name__
        if kind == "StreamEvent":
            text, finish = _event(message, finish)
            streamed = streamed or bool(text)
        elif kind == "AssistantMessage" and not streamed:
            text = _blocks(message)
        elif kind == "ResultMessage":
            _require_success(message)
            text = ""
        else:
            text = ""
        if text:
            parts.append(text)
            if on_delta is not None:
                on_delta(text)
    return Answer(text="".join(parts), finish_reason=finish)


def _require_success(message: Any) -> None:
    """The CLI's verdict, raised while it still says something useful.

    MEASURED against claude-agent-sdk 0.2.128: a refused run arrives as
    `subtype='success'`, `is_error=True`, `result='Credit balance is too low'`,
    and the SDK then raises quoting the SUBTYPE — so the exception reaching the
    caller reads "returned an error result: success" and the one actionable
    sentence is thrown away. `is_error` is the flag; the subtype is not.

    Raised rather than returned for the same reason `_frames._require_no_error`
    does it: a refusal also arrives as ordinary assistant text, and returning it
    puts an outage in the walkthrough as if the model had narrated it.
    """
    if not getattr(message, "is_error", False):
        return
    reason = str(getattr(message, "result", "") or "").strip()
    raise ProviderError(f"the Claude CLI refused the run: {reason}"
                        if reason else "the Claude CLI refused the run")


def _event(message: Any, finish: str) -> tuple[str, str]:
    """A raw stream event: its text, and the finish reason so far.

    `include_partial_messages` is what makes these arrive at all — without it
    the run reports only whole messages and nothing streams.
    """
    event = cast("dict[str, Any]", getattr(message, "event", None) or {})
    delta = cast("dict[str, Any]", event.get("delta") or {})
    kind = event.get("type")
    if kind == "content_block_delta":
        return str(delta.get("text") or ""), finish
    if kind == "message_delta" and delta.get("stop_reason") == "max_tokens":
        return "", "length"        # OpenAI's word: what the callers switch on
    return "", finish


def _blocks(message: Any) -> str:
    """The fallback for SDK builds that emit no partial messages at all.

    Guarded by `streamed` at the call site, never here: on a modern build both
    shapes arrive, and counting each one would double every answer.
    """
    blocks = cast("list[Any]", getattr(message, "content", None) or [])
    return "".join(str(getattr(block, "text", "") or "") for block in blocks)
