"""What a tool call returns — one record, and the one way a failure is shaped.

The same split the HTTP transport makes between `messages` and `replies`, for
the same reason: a failure that each call site formats its own way is a failure
an agent cannot parse. Here that matters more than usual, because the reader is
a model — `isError` tells it not to trust the text as an answer, and the code
in the text tells it what to do about it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..._errors import MegabrainError

__all__ = ["Answer", "answer", "failure", "from_engine"]


@dataclass(frozen=True, slots=True)
class Answer:
    """Text for the agent, and whether it is an answer or an apology."""

    text: str
    failed: bool = False


def answer(text: str) -> Answer:
    return Answer(text=text)


def failure(message: str, code: str = "error") -> Answer:
    """The machine-readable half travels IN the text: MCP has no error field
    of its own beyond the `isError` flag, and a code the agent can match on is
    what turns "it failed" into "run megabrain index"."""
    return Answer(text=f"error ({code}): {message}", failed=True)


def from_engine(err: MegabrainError) -> Answer:
    """A typed engine failure, translated ONCE.

    The taxonomy carries its own stable code, so a new error type reaches this
    surface correctly the day it is added rather than the day someone
    remembers to map it.
    """
    return failure(str(err), err.code)
