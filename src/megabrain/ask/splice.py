"""Replacing every citation with the real bytes.

The rule the whole feature rests on: **the explanation comes from the model,
every line of code comes from the index.** A model that pastes code writes code
that does not exist — confidently, in the house style, with the right names —
and a reader cannot tell. Here it can only point.

Anything the model wrote that LOOKS like code is dropped rather than passed
through: a fenced block in the response is either a citation the engine will
fill in, or an invention.
"""

from __future__ import annotations

import os
import re

from ..retrieval.render import lang_of
from ..storage.model import ChunkMeta
from .citations import CITATION, Citation, parse_citations

__all__ = ["splice", "SPLICE_CAP"]

# A whole-chunk citation longer than this narrows to the cited region. The
# prompt already asks for a sub-range on a big chunk; when the model ignores
# that, the reader eats 180 lines for a two-line claim. The net is
# deterministic, prompt compliance is not.
SPLICE_CAP = int(os.environ.get("MEGABRAIN_ASK_SPLICE_CAP", "70"))

_FENCE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)


def splice(answer: str, candidates: list[ChunkMeta]) -> str:
    """The model's prose with every citation replaced by verbatim code."""
    seen: set[tuple[int, int, str]] = set()
    prose = _FENCE.sub("", answer)      # whatever it tried to paste, it may not

    def replace(match: "re.Match[str]") -> str:
        citation = parse_citations(match.group(0))
        return _blocks(citation[0], candidates, seen) if citation else ""

    return CITATION.sub(replace, prose)


def _blocks(citation: Citation, candidates: list[ChunkMeta],
            seen: set[tuple[int, int, str]]) -> str:
    """One fenced block per cited range, or nothing.

    A citation of a chunk that was never offered is DROPPED rather than
    printed: a missing block is better than `[[99]]` sitting in the middle of
    a sentence, which is what leaks when a regex misses.
    """
    if not 0 <= citation.index < len(candidates):
        return ""
    chunk = candidates[citation.index]
    ranges = citation.ranges or ((chunk.start_line, chunk.end_line),)
    out = [_one(chunk, low, high, seen) for low, high in ranges]
    return "\n".join(block for block in out if block)


def _one(chunk: ChunkMeta, low: int, high: int,
         seen: set[tuple[int, int, str]]) -> str:
    low, high = _narrow(chunk, low, high)
    key = (low, high, chunk.file)
    if key in seen:
        # Models cite their own evidence again when they summarise, and the
        # reader scrolls the same forty lines a second time.
        return ""
    seen.add(key)
    body = _lines(chunk, low, high)
    if not body:
        return ""
    return (f"\n**`{chunk.file}` L{low}-{high}**\n"
            f"```{lang_of(chunk.file)}\n{body}\n```\n")


def _narrow(chunk: ChunkMeta, low: int, high: int) -> tuple[int, int]:
    """Keep a citation inside its chunk, and keep a huge one readable.

    A point citation (`low == high`) widens to a window rather than pasting one
    naked line: one line explains nothing, and the model that cited it was
    pointing at a place, not a statement.
    """
    low = max(low, chunk.start_line)
    high = min(high, chunk.end_line)
    if low == high:
        low, high = max(chunk.start_line, low - 4), min(chunk.end_line, high + 8)
    if high - low + 1 > SPLICE_CAP:
        high = low + SPLICE_CAP - 1
    return low, high


def _lines(chunk: ChunkMeta, low: int, high: int) -> str:
    """The requested lines of the chunk's own text, verbatim."""
    text = (chunk.text or "").split("\n")
    start = max(0, low - chunk.start_line)
    return "\n".join(text[start:start + (high - low + 1)]).rstrip()
