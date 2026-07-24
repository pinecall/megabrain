"""Server-sent events, framed.

Its own module because the format has three rules that are easy to get subtly
wrong and impossible to notice from the server side — the browser just goes
quiet.
"""

from __future__ import annotations

import json

__all__ = ["frame", "SSE_HEADERS"]

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    # Two headers about intermediaries, both learned the hard way: a proxy
    # that buffers delivers the whole stream at the end (which is a slow
    # non-stream), and one that caches serves a finished run to the next
    # caller as if it were live.
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def frame(event: str, data: object) -> bytes:
    """One SSE frame: an event name, JSON data, terminated by a BLANK line.

    The blank line is the whole protocol — without it the browser holds
    everything in its buffer waiting for a delimiter that never comes, which
    looks exactly like a server that stopped responding. The JSON is forced
    onto one line for the same reason: a raw newline inside `data:` ends the
    field, and the remainder is parsed as a new one.
    """
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()
