"""Building an answer: the three ways a route returns one.

Apart from the records in `messages` because these encode POLICY — one error
shape for every failure, and one translation of the engine's taxonomy — and a
policy stated once is a policy no route can quietly disagree with.
"""

from __future__ import annotations

from ..._errors import MegabrainError
from .messages import Reply

__all__ = ["json_reply", "error_reply", "from_engine"]


def json_reply(payload: object, status: int = 200) -> Reply:
    return Reply(status=status, payload=payload)


def error_reply(status: int, message: str, code: str = "error") -> Reply:
    """One error SHAPE for every failure, so a client parses one thing.

    `code` is the machine-readable half — the same stable string the engine's
    error taxonomy carries, not the HTTP status, which several causes share.
    """
    return Reply(status=status, payload={"error": message, "code": code})


def from_engine(err: MegabrainError) -> Reply:
    """A typed engine failure, translated ONCE.

    The taxonomy carries its own status and code, so no route invents an HTTP
    status of its own — and a new error type reaches every endpoint correctly
    the day it is added, instead of the four that remembered to map it.
    """
    return error_reply(err.http_status, str(err), err.code)
