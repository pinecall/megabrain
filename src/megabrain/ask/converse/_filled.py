"""One extra round when the answer admitted it wrote without a body.

Split from the conversation loop because it is a different decision: that loop
serves what the model ASKED for, and this serves what it said it did not have.
MEASURED at 1 answer in 14, where the resulting prose hedged about behaviour the
missing code states outright — `dispatch!` puts sinatra's after filters in an
`ensure`, so "may or may not run" was never true.

Served as a normal turn rather than patched in afterwards, so the model writes
ONE complete answer with the material. The widening below the prose could quote
the body but never un-hedge the sentence above it.
"""

from __future__ import annotations

from typing import Any, Callable

from ...providers.chat import Answer, ChatProvider
from ...storage import Store
from ..events import Emit
from ._admits import admitted_gap
from ._missing import FILL, missing_bodies

__all__ = ["filled"]


def filled(provider: ChatProvider, answer: Answer, messages: list[dict[str, Any]],
           store: Store, body: Callable[..., dict[str, Any]], *,
           emit: Emit, on_delta: Any = None) -> Answer:
    """The answer again, with the bodies it said it lacked — or unchanged.

    ONE retry, and only on an admission the engine can satisfy: a confession
    about code the index does not hold would otherwise buy a second identical
    answer at full price. `body` is passed in rather than imported to keep the
    request shape owned by the loop that talks to the provider.
    """
    if not admitted_gap(answer.text):
        return answer
    bodies = missing_bodies(store, answer.text)
    if not bodies:
        return answer
    emit({"type": "filling", "chars": len(bodies)})
    messages = [*messages, {"role": "assistant", "content": answer.text},
                {"role": "user", "content": FILL + bodies}]
    return provider.stream_chat(body(provider, messages), on_delta=on_delta)
