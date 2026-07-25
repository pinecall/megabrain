"""Turning a model's tool request into the messages the API expects.

Split from the loop because it is a different job: the loop decides WHEN to
keep going, this decides what one request MEANT. It is also the only place that
touches the wire shape of a tool turn, so a backend quirk lands here rather
than inside the conversation.

Everything here answers rather than raises. `arguments` is raw JSON a model
produced, so it can be malformed, and the layer holding the schema is the one
that decides what that means — a complaint returned AS the tool's result lets
the model correct itself, where an exception ends a turn the reader is waiting
on.
"""

from __future__ import annotations

import json
from typing import Any

from ..providers.chat import Answer, ToolCall
from ..storage import Store
from .events import Emit
from .tools import open_file

__all__ = ["assistant_turn", "tool_result"]


def assistant_turn(answer: Answer) -> dict[str, Any]:
    """The model's own turn, echoed back — the API rejects a tool result whose
    request is not in the transcript."""
    return {"role": "assistant", "content": answer.text or None,
            "tool_calls": [{"id": call.id, "type": "function",
                            "function": {"name": call.name,
                                         "arguments": call.arguments}}
                           for call in answer.tool_calls]}


def tool_result(store: Store, call: ToolCall, emit: Emit) -> dict[str, Any]:
    """One tool executed, as a `tool` message."""
    path, args = "", {}
    try:
        args = json.loads(call.arguments or "{}")
        path = str(args.get("path", ""))
    except (ValueError, AttributeError):
        content = f"`{call.arguments}` is not valid JSON — send {{\"path\": \"…\"}}"
    else:
        content = (open_file(store, path, _line(args, "from_line"),
                             _line(args, "to_line")) if path
                   else 'missing "path" — send {"path": "lib/app.rb"}')
    emit({"type": "opened", "file": path, "chars": len(content)})
    return {"role": "tool", "tool_call_id": call.id, "content": content}


def _line(args: dict[str, Any], key: str) -> int:
    """A line number the model sent, or 0. Models send "42" as often as 42, and
    a string here would silently slice nothing."""
    try:
        return max(0, int(args.get(key) or 0))
    except (TypeError, ValueError):
        return 0
