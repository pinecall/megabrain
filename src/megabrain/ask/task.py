"""The TASK path: let the narrator open files, then hand back the edit surface.

The question path narrates a mechanism from chunks cosine chose — the wrong
input for a change, and the difference was measured. Asked to add a helper,
`ask` explained how redirection works and the agent had to come back with "and
where is that defined?": a whole extra round trip to learn where to type.

So here the model gets a TOOL. It opens what it needs from the index and writes
the surface: each file to touch, the line to touch it at, the neighbouring
example to imitate — existing code arriving as citations megabrain replaces
with verbatim source.

What it deliberately does NOT hand back is a prepared edit batch. That was
tried and MEASURED on two tasks: both times the pre-built operation was WRONG —
once the hole landed inside an `except` block it was supposed to precede, once
the operation pointed at a test file where the mirrored function has no tests
at all — and both agents threw it away and built their own `replace` from the
quoted anchor. It also cost the most tokens in the answer, quoting the anchor a
third time. Guessing the exact edit is not something this engine can be right
about; showing the reader the exact lines is.

Bounded and fail-open: a model that keeps browsing stops at MAX_ROUNDS, and a
backend with no tool support still returns its text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import Bundle
from ..providers.chat import Answer, ChatProvider
from ..storage import Store
from ._callees import named_definitions
from ._enclosing import enclosing_bodies
from ._headers import already_imported
from ._pinned import exercising_tests
from ._quote import quote_citations
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
        # Every widening reads the RAW text and appends more citations, so all
        # of them are spliced by the same single quoting pass at the end.
        widened = (answer.text + enclosing_bodies(store, answer.text)
                   + named_definitions(store, answer.text)
                   + exercising_tests(store, answer.text)
                   + already_imported(store, answer.text))
        surface = quote_citations(widened, store)
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
