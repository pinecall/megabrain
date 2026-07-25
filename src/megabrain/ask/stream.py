"""Splicing while the answer is still arriving.

The hard part of streaming a cited walkthrough: a citation can be cut in half
by a delta boundary. `[[3:70` at the end of a buffer is neither prose nor a
citation yet, and emitting it as prose cannot be taken back — the reader has
already seen `[[3:70` in the middle of a sentence.

So the tail is HELD until it is decidable. Everything before it flushes
immediately, which is what keeps the answer live.
"""

from __future__ import annotations

from ..storage.model import ChunkMeta
from .citations import PARTIAL
from .splice import splice

__all__ = ["Splicer"]


class Splicer:
    """Feed it deltas, get spliced markdown out — as it becomes decidable."""

    def __init__(self, candidates: list[ChunkMeta]) -> None:
        self._candidates = candidates
        self._held = ""

    def feed(self, delta: str) -> str:
        """The part of `delta` that can be emitted now, already spliced."""
        buffered = self._held + delta
        cut = _decidable(buffered)
        self._held = buffered[cut:]
        return splice(buffered[:cut], self._candidates) if cut else ""

    def flush(self) -> str:
        """Whatever is left once the stream ends.

        Two half-written things are DROPPED rather than emitted, because at
        this point neither can ever complete:

        * a citation — `[[0:` in the middle of a sentence is litter, and a
          missing block is the better failure;
        * an unterminated fence — the model died part-way through pasting
          code it invented, and `splice` only removes fences that CLOSE. Left
          alone it would sail through as prose, which is invariant #5 failing
          in exactly the case nobody tests.
        """
        remaining, self._held = self._held, ""
        return splice(_drop_unfinished(remaining), self._candidates)


def _drop_unfinished(remaining: str) -> str:
    """Cut the tail back to the last point that is still honest text."""
    partial = PARTIAL.search(remaining)
    if partial:
        remaining = remaining[:partial.start()]
    if remaining.count("```") % 2 == 1:
        remaining = remaining[:remaining.rfind("```")]
    return remaining


def _decidable(buffered: str) -> int:
    """How much of the buffer is safe to emit.

    Everything up to a citation that is still being written. A fenced block
    counts as undecidable too: the model may be part-way through one, and
    `splice` deletes fences whole — half a fence would sail through as prose.
    """
    partial = PARTIAL.search(buffered)
    cut = partial.start() if partial else len(buffered)
    fence = buffered.rfind("```", 0, cut)
    if fence != -1 and buffered.count("```", 0, cut) % 2 == 1:
        return fence
    return cut
