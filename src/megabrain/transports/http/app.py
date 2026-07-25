"""Building and running the server.

Threaded rather than async: the engine is numpy and sqlite, and every use case
is synchronous. A thread per request calls them directly, which is the whole
of the concurrency story — no event loop, no async twin of the engine, and no
third-party server to depend on.
"""

from __future__ import annotations

import sys
from http.server import ThreadingHTTPServer
from socketserver import BaseServer
from typing import cast

from ._handler import Handler
from .security import Guard, Policy

__all__ = ["build_server", "serve", "bound_port", "LOOPBACK"]

LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", ""})


class _Server(ThreadingHTTPServer):
    """The server owns the guard; the handler reads it off `self.server`."""

    daemon_threads = True             # a stuck request must not hold up shutdown

    def __init__(self, address: tuple[str, int], guard: Guard) -> None:
        self.guard = guard
        super().__init__(address, Handler)

    def handle_error(self, request: object, client_address: object) -> None:
        """A client hanging up is not a server error.

        With keep-alive the socket sits waiting for a request that never
        comes, and every closed tab arrives here as a ConnectionResetError.
        The default prints a full traceback for each one, which fills the log
        with noise and trains everyone to ignore it — including the day it
        says something real.
        """
        if not isinstance(sys.exc_info()[1], (ConnectionError, BrokenPipeError)):
            super().handle_error(request, client_address)  # type: ignore[arg-type]


def build_server(host: str, port: int, policy: Policy | None = None) -> BaseServer:
    """A bound server, not yet serving — so a test can take the real port.

    Refuses to expose an unauthenticated API beyond this machine. Indexing is
    a WRITE endpoint that reads any path the process can reach, so an open
    bind on a shared network is not a warning, it is a mistake with a blast
    radius. Set a token to bind publicly.
    """
    policy = policy or Policy()
    if host not in LOOPBACK and not policy.token:
        raise ValueError(
            f"refusing to bind {host} without a token — every route, including "
            f"indexing, would be open to the network. Pass a token, or bind "
            f"127.0.0.1 and put a reverse proxy in front.")
    return _Server((host, port), Guard(policy))


def bound_port(server: BaseServer) -> int:
    """The port actually in use.

    Worth a function: `port=0` asks the OS to choose, so the number is only
    knowable after binding — and the stdlib types `server_address` as a union
    because AF_UNIX servers have no port at all.
    """
    return cast("tuple[str, int]", server.server_address)[1]


def serve(host: str = "127.0.0.1", port: int = 2137,
          policy: Policy | None = None) -> None:
    """Run until interrupted."""
    server = build_server(host, port, policy)
    try:
        server.serve_forever()
    finally:
        server.server_close()
