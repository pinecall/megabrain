"""Framing a citation around the line that matters.

Its own module because it is a display decision, not a retrieval one: WHICH
chunk to cite is `_pinned`'s question, and how much of it the reader can
actually see is this one.
"""

from __future__ import annotations

import re

__all__ = ["window_around", "CONTEXT_LINES", "WINDOW_LINES"]

CONTEXT_LINES = 4
"""Lines shown above the mention, so it arrives inside its own test rather than
mid-body."""

WINDOW_LINES = 28
"""Span cited around a mention. Under the display cap on purpose — a citation
that gets truncated before its point looks checked and is not."""


def window_around(text: str, first_line: int, wanted: re.Pattern[str]) -> tuple[int, int]:
    """A tight span around the first mention, not the chunk that holds it.

    That chunk was 257 lines with the mention 166 lines in — past the display
    cap, so citing it would have pointed at the right place and shown the wrong
    part. A citation whose point is cut off looks checked and is not.
    """
    lines = text.split("\n")
    hit = next((n for n, line in enumerate(lines) if wanted.search(line)), 0)
    start = first_line + max(0, hit - CONTEXT_LINES)
    return start, start + WINDOW_LINES - 1
