"""The retrieved chunks as prompt text: the best few with code, the rest listed.

Shared by every deliverable that shows a model what retrieval found, because the
BALANCE here is measured and must not drift between them.

Two numbers carry it. `MAX_BODIES` is why a model opens files at all: served all
thirty bodies — 165 000 characters — the narrator called `open_file` zero times
across four questions, one of which said "open this file" outright. And every
line is prefixed with its ABSOLUTE file line number, because unnumbered, the
sub-range citations landed a few lines off and cut functions mid-body.
"""

from __future__ import annotations

import os

from ...storage.model import ChunkMeta

__all__ = ["chunk_blocks", "MAX_BODIES", "MAX_CTX_CHARS"]

# ~50K tokens of candidate code, which fits every default cloud model. A local
# runtime has a smaller window and will TRUNCATE the prompt silently, so it is
# overridable rather than baked in.
MAX_CTX_CHARS = int(os.environ.get("MEGABRAIN_ASK_CTX_CHARS", "200000"))

MAX_BODIES = int(os.environ.get("MEGABRAIN_ASK_BODIES", "8"))
"""Chunks quoted with their code. The rest are LISTED, and openable.

MEASURED, and it is the difference between a tool that reads and one that
guesses. Eight is the best code retrieval found; the rest arrive as a MAP the
model opens from — the régime the retired `megabrain_code` ran in, where opening
was measured at two files per task."""


def chunk_blocks(candidates: list[ChunkMeta]) -> str:
    """Numbered bodies up to the cap, then one head line each for the rest."""
    blocks: list[str] = []
    used = 0
    for index, chunk in enumerate(candidates):
        if index >= MAX_BODIES:
            # Listed, not quoted. The head alone is the citable index plus where
            # the code lives, which is exactly what `open_file` needs.
            blocks.append(head(index, chunk))
            continue
        body = _numbered(chunk)
        if used + len(body) > MAX_CTX_CHARS:
            # Truncated HERE, visibly, rather than by the serving runtime —
            # which drops the tail of the prompt without telling anyone.
            body = body[:2000] + "\n# …truncated…\n"
        used += len(body)
        blocks.append(f"{head(index, chunk)}\n{body}")
    return "\n".join(blocks)


def head(index: int, chunk: ChunkMeta) -> str:
    """The citable index, and where the chunk lives.

    `[k]` single-bracketed on purpose: the model cites with `[[k]]`, and a
    header that already looked like a citation invited it to echo the header.
    """
    name = f" ({chunk.name})" if chunk.name else ""
    return f"[{index}] {chunk.file} L{chunk.start_line}-{chunk.end_line}{name}"


def _numbered(chunk: ChunkMeta) -> str:
    """Chunk text with every line prefixed by its absolute file line number."""
    start = chunk.start_line
    return "".join(f"{start + offset}| {line}"
                   for offset, line in enumerate((chunk.text or "").splitlines(True)))
