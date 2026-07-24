"""What a route receives and returns.

Two plain records, so a route is a pure function of its input: no socket, no
handler, no server. That is what lets the routes be tested directly and the
socket work be tested once, instead of every route paying for a live port.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator
from urllib.parse import parse_qs, urlsplit

from .security import Policy

__all__ = ["Request", "Reply", "Route", "Frames", "json_reply", "error_reply",
           "split_target"]

Frames = Callable[[], Iterator[tuple[str, object]]]
"""A lazy source of SSE frames: (event name, JSON-serialisable data).

A callable rather than an iterator, so nothing starts running until the
response headers are on the wire — a stream that begins computing during
routing can no longer report its own failure as an HTTP status.
"""


def _no_query() -> dict[str, str]:
    return {}


def _no_body() -> dict[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=_no_query)
    body: dict[str, Any] = field(default_factory=_no_body)
    policy: Policy = Policy()
    """What this deployment allows.

    Part of the request rather than smuggled through the body: a route that
    reports its own constraints is asking about the CONTEXT of the call, and
    context that travels as a magic key is context nobody can find.
    """

    def param(self, name: str, default: str = "") -> str:
        """A value from the query string OR the JSON body, in that order.

        The studio sends the same field one way for GET and the other for
        POST; a route should not have to care which door it came through.
        """
        found = self.query.get(name, self.body.get(name, default))
        return found if isinstance(found, str) else default


@dataclass(frozen=True, slots=True)
class Reply:
    """A finished answer. `stream` is set instead of `payload` for SSE."""

    status: int = 200
    payload: object = None
    stream: Frames | None = None      # set INSTEAD of payload, for SSE


Route = Callable[[Request], Reply]


def json_reply(payload: object, status: int = 200) -> Reply:
    return Reply(status=status, payload=payload)


def split_target(target: str) -> tuple[str, dict[str, str]]:
    """A raw request target -> (path, query).

    Only the FIRST value per key survives: a repeated key is a client bug, and
    quietly taking the last one hides it. A trailing slash is stripped so
    `/health` and `/health/` are one route rather than a 404 nobody expects.
    """
    parts = urlsplit(target)
    return parts.path.rstrip("/") or "/", {
        key: values[0] for key, values in parse_qs(parts.query).items() if values}


def error_reply(status: int, message: str, code: str = "error") -> Reply:
    """One error SHAPE for every failure, so a client parses one thing.

    `code` is the machine-readable half — the same stable string the engine's
    error taxonomy carries, not the HTTP status, which several causes share.
    """
    return Reply(status=status, payload={"error": message, "code": code})
