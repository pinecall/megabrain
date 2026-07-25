"""The one exception this transport raises at itself.

Alone in a module so both argument readers can raise it without either
importing the other — a shared vocabulary word belongs above the things that
share it, not inside one of them.
"""

from __future__ import annotations

__all__ = ["Missing"]


class Missing(Exception):
    """A required argument the caller did not send.

    Private vocabulary: it never leaves the transport — `call_tool` turns it
    into an ordinary failed Answer naming the argument, because a KeyError
    three frames down reaches the host as a dead tool call.
    """
