"""Putting a Reply onto the socket.

Apart from the handler because it answers a different question: the handler
decides WHAT to answer, this decides how that becomes bytes. It is also the
half with the protocol traps — chunk framing, and flushing.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from .messages import Frames, Reply
from .sse import SSE_HEADERS, frame

__all__ = ["write_reply"]


def write_reply(handler: BaseHTTPRequestHandler, reply: Reply, *,
                body: bool = True) -> None:
    """`body=False` writes the headers only — that is what HEAD is.

    The Content-Length still describes the body a GET would return, which is
    the whole point: a caller uses HEAD to learn the size without paying for
    the bytes.
    """
    stream = reply.stream
    if stream is not None:
        return _write_stream(handler, reply.status, stream)
    payload = reply.body if reply.body is not None else json.dumps(reply.payload).encode()
    handler.send_response(reply.status)
    handler.send_header("Content-Type", reply.content_type)
    # Declared explicitly: under HTTP/1.1 keep-alive a response without a
    # length or chunked framing leaves the client waiting for a body that has
    # already fully arrived.
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    if body:
        handler.wfile.write(payload)


def _write_stream(handler: BaseHTTPRequestHandler, status: int, frames: Frames) -> None:
    """Chunked, and FLUSHED per frame — an unflushed event stream is just a
    slow ordinary response, which is the bug streaming exists to avoid."""
    handler.send_response(status)
    for header, value in SSE_HEADERS.items():
        handler.send_header(header, value)
    handler.send_header("Transfer-Encoding", "chunked")
    handler.end_headers()
    try:
        for event, data in frames():
            _chunk(handler, frame(event, data))
    except (BrokenPipeError, ConnectionResetError):
        return                     # the client navigated away; not an error
    _chunk(handler, b"")           # the zero-length chunk that ends the body


def _chunk(handler: BaseHTTPRequestHandler, body: bytes) -> None:
    handler.wfile.write(f"{len(body):X}\r\n".encode() + body + b"\r\n")
    handler.wfile.flush()
