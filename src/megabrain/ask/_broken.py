"""Finding the references in an answer that resolve to nothing.

Two shapes, both of which reach a reader as a file path with no code under it —
and both of which read like an answer:

    `src/x/y.py` L688-757    the model named a file instead of citing a chunk
    [[not-a-number]]         a citation the grammar cannot parse

Detected on the RAW model output, before splicing: afterwards a resolved
citation has become a code block, so whatever still looks like a reference is
exactly what failed.
"""

from __future__ import annotations

import re

from .citations import CITATION
from .splice import BLOCK_HEADER

__all__ = ["broken_references"]

# `path.ext` followed by a line range: the shape a model falls back to when it
# forgets it may not write code. The EXTENSION is what keeps this from matching
# ordinary inline code like `handle()` or `SSEDecoder`.
_PROSE_REF = re.compile(r"`[^`\n]+\.[A-Za-z0-9]+`\s*L\d+(?:\s*-\s*\d+)?")

# Anything double-bracketed that the citation grammar did not accept.
_ANY_BRACKETED = re.compile(r"\[\[[^\]\n]*\]\]")


def broken_references(answer: str) -> list[str]:
    """Every fragment that names code but resolves to nothing.

    The engine's OWN block headers are removed first. They have the same shape
    as the mistake being hunted, and today this is only safe because detection
    runs before splicing — one call on a rendered answer would flag every
    correct block and send the whole thing back to be "repaired".
    """
    answer = BLOCK_HEADER.sub("", answer)
    resolved = {match.group(0) for match in CITATION.finditer(answer)}
    malformed = [match.group(0) for match in _ANY_BRACKETED.finditer(answer)
                 if match.group(0) not in resolved]
    return [*malformed, *(match.group(0) for match in _PROSE_REF.finditer(answer))]
