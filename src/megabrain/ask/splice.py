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

from ..storage.model import ChunkMeta
from ._block import fenced_block
from .citations import CITATION, Citation, parse_citations

__all__ = ["splice", "SPLICE_CAP", "BLOCK_HEADER"]

# A whole-chunk citation longer than this narrows to the cited region. The
# prompt already asks for a sub-range on a big chunk; when the model ignores
# that, the reader eats 180 lines for a two-line claim. The net is
# deterministic, prompt compliance is not.
SPLICE_CAP = int(os.environ.get("MEGABRAIN_ASK_SPLICE_CAP", "70"))

_FENCE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)

# The header written above every spliced block, defined HERE because this is
# what writes it. Two other places have to RECOGNISE it — the broken-reference
# detector, which would otherwise flag every correct block, and the flow cache,
# which must strip it before a stored answer goes back to a model.
BLOCK_HEADER = re.compile(r"\*\*`[^`\n]+`\s*L\d+(?:-\d+)?\*\*[^\n]*")


def splice(answer: str, candidates: list[ChunkMeta]) -> str:
    """The model's prose with every citation replaced by verbatim code."""
    seen: set[tuple[int, int, str]] = set()
    prose = _FENCE.sub("", answer)      # whatever it tried to paste, it may not

    def replace(match: "re.Match[str]") -> str:
        # One pair of brackets can hold several references — the grouped form
        # models write unprompted — so every one of them becomes a block.
        return "".join(_blocks(citation, candidates, seen)
                       for citation in parse_citations(match.group(0)))

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
    out = [fenced_block(chunk, *_narrow(chunk, low, high), seen)
           for low, high in ranges]
    return "\n".join(block for block in out if block)


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
