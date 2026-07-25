"""Reading a raw request target off the wire.

Its own module, small as it is: this is the one place a percent-encoded string
from a stranger becomes the path a router matches and the params a route reads,
and every rule about that decoding belongs where it can be read at once.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

__all__ = ["split_target"]


def split_target(target: str) -> tuple[str, dict[str, str]]:
    """A raw request target -> (path, query).

    Only the FIRST value per key survives: a repeated key is a client bug, and
    quietly taking the last one hides it. A trailing slash is stripped so
    `/health` and `/health/` are one route rather than a 404 nobody expects.
    """
    parts = urlsplit(target)
    return parts.path.rstrip("/") or "/", {
        key: values[0] for key, values in parse_qs(parts.query).items() if values}
