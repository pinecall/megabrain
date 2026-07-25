"""The TASK path: let the narrator open files, then hand back the edit surface.

The question path narrates a mechanism from chunks cosine chose — the wrong
input for a change, and the difference was measured. Asked to add a helper,
`ask` explained how redirection works and the agent had to come back with "and
where is that defined?": a whole extra round trip to learn where to type.

So here the model gets a TOOL. It opens what it needs from the index and writes
the surface: each file to touch, the line to touch it at, the neighbouring
example to imitate — existing code arriving as citations megabrain replaces
with verbatim source.

Bounded and fail-open: a model that keeps browsing stops at MAX_ROUNDS, and a
backend with no tool support still returns its text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import Bundle
from ..providers.chat import Answer, ChatProvider
from ..storage import Store
from ._operations import operations_from
from ._quote import quote_citations
from ._surface import apply_block
from ._taskprompt import build_task_prompt
from ._toolcall import assistant_turn, tool_result
from .events import Emit, emit_nothing
from .tools import TOOLS

__all__ = ["walk_task", "MAX_ROUNDS", "MAX_TOKENS"]

MAX_ROUNDS = 5
"""Tool rounds before the model is made to conclude.

Each round is one model call plus one file, and a task's surface is two or
three files — five leaves room to open a wrong one and recover, without letting
a model that keeps browsing spend the caller's afternoon.
"""

MAX_TOKENS = 3000


def walk_task(provider: ChatProvider, task: str, bundle: Bundle, root: Path, *,
              emit: Emit = emit_nothing) -> str:
    """The edit surface for `task`, with every cited line spliced verbatim.

    Opens the index itself and holds it for the whole loop: the tool reads
    files and the citations read lines, and both must see the same index the
    bundle came from.
    """
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_task_prompt(task, bundle)}]
    answer = Answer(text="")
    with Store(root) as store:
        for _round in range(MAX_ROUNDS):
            answer = provider.stream_chat(_body(provider, messages))
            if not answer.tool_calls:
                break
            messages.append(assistant_turn(answer))
            for call in answer.tool_calls:
                messages.append(tool_result(store, call, emit))
        # Operations come from the RAW text: the anchors are still citations
        # here, and quoting turns them into code blocks that no longer say
        # which lines they were.
        operations = operations_from(answer.text, store)
        surface = quote_citations(answer.text, store) + apply_block(operations)
    # Emitted, not merely returned. Every surface renders from the event
    # stream — the CLI, the HTTP route and the studio all print `delta` — so a
    # path that only returns its text arrives as a blank answer everywhere.
    emit({"type": "delta", "text": surface})
    return surface


def _body(provider: ChatProvider, messages: list[dict[str, Any]]) -> dict[str, Any]:
    # `parallel_tool_calls` is the half the PROMPT cannot do. Asked in words to
    # open every file at once, the model still emitted one call per turn —
    # measured at 908 + 838 ms of pure round trip on a two-file change, 45% of
    # the call. Backends that do not know the field ignore it.
    return {"model": getattr(provider, "model", ""), "messages": messages,
            "tools": TOOLS, "parallel_tool_calls": True,
            "max_tokens": MAX_TOKENS, "temperature": 0}
