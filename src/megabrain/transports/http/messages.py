"""What a route receives and returns — the two records, and nothing else.

Plain records, so a route is a pure function of its input: no socket, no
handler, no server. That is what lets the routes be tested directly and the
socket work be tested once, instead of every route paying for a live port.

The functions that BUILD a `Reply` live in `replies`, and turning a raw request
target into these fields lives with the handler that reads the wire. Records
here, construction there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from .security import Policy

__all__ = ["Request", "Reply", "Route", "Frames"]

Frames = Callable[[], Iterator[tuple[str, object]]]
"""SSE frames — (event name, data) — behind a callable, so nothing runs until
the headers are on the wire. A stream that starts computing during routing can
no longer report its own failure as an HTTP status."""


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

    def repo(self) -> Path:
        """Which repository to answer for, defaulting to this process's own
        directory — what a headless single-repo deployment wants.

        A method rather than a helper each route keeps privately: four had
        written this line, and a default that disagrees between two endpoints
        is a bug nobody reproduces.
        """
        return Path(self.param("repo") or ".")


@dataclass(frozen=True, slots=True)
class Reply:
    """A finished answer, in exactly one of three shapes.

    `payload` is JSON, `stream` is SSE, `body` is raw bytes. Three fields
    rather than one `object` because the writer has to know which one it is
    holding, and inferring that from the value's type is how a bytes payload
    ends up JSON-encoded as a list of integers.
    """

    status: int = 200
    payload: object = None
    stream: Frames | None = None      # set INSTEAD of payload, for SSE
    body: bytes | None = None         # set INSTEAD of payload, for a file
    content_type: str = "application/json"


Route = Callable[[Request], Reply]
