"""Letting the narrator OPEN files until it has what the question needs.

Retrieval hands over the chunks cosine chose, which is a good start and never
the whole answer: the span that matters can sit fifty lines below the chunk that
matched, and a walkthrough of a big ugly repository needs the file, not the
excerpt. So the model gets a tool and keeps reading until it stops asking.

MEASURED, on the path this replaces: asked where a helper was defined, the
narrator explained the mechanism and the caller had to come back with "and where
is that defined?" — a whole extra round trip to learn something the engine could
have opened itself.

Bounded and fail-open: a model that keeps browsing stops at MAX_ROUNDS, and a
backend with no tool support returns its text on the first pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..providers.chat import Answer, ChatProvider
from ..storage import Store
from ._toolcall import assistant_turn, tool_result
from .events import Emit
from .tools import TOOLS

__all__ = ["answered", "converse", "MAX_ROUNDS"]

MAX_ROUNDS = 5
"""Rounds of opening before the model is made to conclude.

Each round is one model call plus the files it asked for, and a walkthrough
needs two or three — five leaves room to open a wrong one and recover, without
letting a model that keeps browsing spend the caller's afternoon.
"""


def answered(provider: ChatProvider, prompt: str, root: Path | None, *,
             emit: Emit, on_delta: Any = None) -> Answer:
    """The model's final text, after any files it asked to open.

    Without a `root` there is no index to open FROM, so one buffered call is the
    whole answer — the multi-agent path narrates that way, and a walkthrough
    that refused to run without a root would break it.
    """
    if root is None:
        return provider.stream_chat(
            {"model": getattr(provider, "model", ""), "max_tokens": 2400,
             "temperature": 0, "messages": [{"role": "user", "content": prompt}]},
            on_delta=on_delta)
    with Store(root) as store:
        return converse(provider, prompt, store, emit=emit, on_delta=on_delta)


def converse(provider: ChatProvider, prompt: str, store: Store, *,
             emit: Emit, on_delta: Any = None) -> Answer:
    """Talk until the model stops asking for files; return its final answer."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    answer = Answer(text="")
    for _round in range(MAX_ROUNDS):
        answer = provider.stream_chat(_body(provider, messages), on_delta=on_delta)
        if not answer.tool_calls:
            break
        messages.append(assistant_turn(answer))
        for call in answer.tool_calls:
            messages.append(tool_result(store, call, emit))
    return answer


def _body(provider: ChatProvider, messages: list[dict[str, Any]]) -> dict[str, Any]:
    # `parallel_tool_calls` is the half the PROMPT cannot do. Asked in words to
    # open every file at once, the model still emitted one call per turn —
    # measured at 908 + 838 ms of pure round trip on two files, 45% of the call.
    # Backends that do not know the field ignore it.
    return {"model": getattr(provider, "model", ""), "messages": messages,
            "tools": TOOLS, "parallel_tool_calls": True,
            "max_tokens": 2400, "temperature": 0}
