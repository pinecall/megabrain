"""Reading one OpenAI-compatible SSE stream.

Its own module because the parsing has four traps and each one fails silently:
a keep-alive comment parsed as data, a tool call that arrives in fragments, an
error delivered INSIDE a 200 response, and a stream that ends without [DONE].
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Iterator, cast

from ..._errors import ProviderError
from .base import Answer, OnDelta, ToolCall

__all__ = ["read_stream"]


def read_stream(lines: Iterable[str], on_delta: OnDelta | None = None) -> Answer:
    """Every delta, concatenated, with the tool calls reassembled.

    Takes an ITERABLE of lines rather than a finished body: `on_delta` has to
    fire while the answer is still arriving, and a function handed the whole
    response can only ever deliver it all at once — streaming in name only.
    """
    text: list[str] = []
    finish = ""
    calls: dict[int, dict[str, str]] = {}
    for event in _events(lines):
        _require_no_error(event)
        choices = cast("list[dict[str, Any]]", event.get("choices") or [])
        choice: dict[str, Any] = choices[0] if choices else {}
        delta: dict[str, Any] = choice.get("delta") or {}
        if content := delta.get("content"):
            text.append(str(content))
            if on_delta is not None:
                on_delta(str(content))
        _merge_calls(calls, cast("list[dict[str, Any]]",
                                 delta.get("tool_calls") or []))
        finish = str(choice.get("finish_reason") or finish)
    return Answer(text="".join(text), finish_reason=finish,
                  tool_calls=[ToolCall(**calls[index]) for index in sorted(calls)])


def _events(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """The JSON payload of each `data:` line.

    Everything else is skipped rather than parsed: providers send `: ping`
    comments to hold the connection open, and a parser that treats one as data
    dies at random intervals on a healthy stream.
    """
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped[5:].strip()
        if payload == "[DONE]":
            return
        try:
            parsed = json.loads(payload)
        except ValueError:
            continue          # a truncated final frame is not worth failing on
        if isinstance(parsed, dict):
            yield parsed


def _require_no_error(event: dict[str, Any]) -> None:
    """A provider can report failure inside a 200 stream.

    Treated as content it becomes part of the answer — which is how an outage
    ends up quoted back to the user as if the model had said it.
    """
    error = event.get("error")
    if not error:
        return
    detail = cast("dict[str, Any]", error).get("message") if isinstance(error, dict) else error
    raise ProviderError(f"chat stream failed: {detail}")


def _merge_calls(calls: dict[int, dict[str, str]],
                 fragments: list[dict[str, Any]]) -> None:
    """Tool calls arrive in pieces: the name in one frame, the arguments split
    across several. Accumulated per index, which is the only field that
    identifies which call a fragment belongs to."""
    for fragment in fragments:
        current = calls.setdefault(int(fragment.get("index", 0)),
                                   {"id": "", "name": "", "arguments": ""})
        if identifier := fragment.get("id"):
            current["id"] = str(identifier)
        function: dict[str, Any] = fragment.get("function") or {}
        if name := function.get("name"):
            current["name"] = str(name)
        current["arguments"] += str(function.get("arguments") or "")
