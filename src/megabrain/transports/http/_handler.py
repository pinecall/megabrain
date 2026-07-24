"""The socket half: parse a request, run the router, write the response.

Everything protocol-specific lives here, so `router` and `routes/` never see a
socket and can be tested as plain functions.

The handler reads its guard off `self.server` rather than closing over one.
The stdlib builds a handler per request, so a factory returning a class means
the whole class body is one function — unreadable, and untestable except
through a port.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, Any, cast

from ._writer import write_reply
from .messages import Reply, Request, error_reply, split_target
from .router import dispatch

if TYPE_CHECKING:
    from .security import Guard

__all__ = ["Handler", "MAX_BODY"]

MAX_BODY = 2_000_000       # a query is words; anything larger is a mistake or an attack


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "megabrain"

    @property
    def guard(self) -> "Guard":
        return self.server.guard          # type: ignore[attr-defined,no-any-return]

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silence. The default writes a line to stderr for EVERY request,
        which turns a studio session into thousands of lines of noise."""

    def do_GET(self) -> None:             # noqa: N802 — the stdlib's spelling
        self._serve("GET")

    def do_POST(self) -> None:            # noqa: N802
        self._serve("POST")

    def _serve(self, method: str) -> None:
        path, query = split_target(self.path)
        refusal = self.guard.refuse(path, authorization=self.headers.get("Authorization", ""),
                                    caller=self.client_address[0])
        if refusal:
            return self._write(error_reply(refusal[0], refusal[1]))
        try:
            body = self._read_body() if method == "POST" else {}
        except ValueError as err:
            return self._write(error_reply(400, str(err), "bad_request"))
        self._write(dispatch(Request(method=method, path=path, query=query,
                                     body=body, policy=self.guard.policy)))

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError(f"body over {MAX_BODY} bytes")
        if not length:
            return {}
        loaded: object = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(loaded, dict):
            raise ValueError("body must be a JSON object")
        # A JSON object's keys are strings by the format's own definition, so
        # this narrowing is a fact about JSON rather than an assumption.
        return cast("dict[str, Any]", loaded)

    def _write(self, reply: Reply) -> None:
        write_reply(self, reply)
