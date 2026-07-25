"""The prompt: numbered candidates, and rules that forbid writing code.

`_numbered` is the load-bearing detail. Each line carries its ABSOLUTE file
line number so the model reads sub-range bounds off the text instead of
counting lines itself — unnumbered, `[[k:lo-hi]]` citations landed a few lines
off and cut functions mid-body. Prompt only: the splice uses the clean text.
"""

from __future__ import annotations

import os

from ..storage.model import ChunkMeta

__all__ = ["build_prompt", "MAX_CTX_CHARS", "RULES"]

from ._rules import RULES

# ~50K tokens of candidate code, which fits every default cloud model. A local
# runtime has a smaller window and will TRUNCATE the prompt silently, so it is
# overridable rather than baked in.
MAX_CTX_CHARS = int(os.environ.get("MEGABRAIN_ASK_CTX_CHARS", "200000"))

def build_prompt(question: str, candidates: list[ChunkMeta],
                 context: str = "") -> str:
    """The cite-only walkthrough prompt over numbered chunks.

    `context` is a previous walkthrough of the same area, prose only. It is
    explicitly NON-CITABLE: the model may use it to know what matters and in
    what order, but every line of code still has to come from a numbered chunk.
    """
    blocks: list[str] = []
    used = 0
    for index, chunk in enumerate(candidates):
        body = _numbered(chunk)
        if used + len(body) > MAX_CTX_CHARS:
            # Truncated HERE, visibly, rather than by the serving runtime —
            # which drops the tail of the prompt without telling anyone.
            body = body[:2000] + "\n# …truncated…\n"
        used += len(body)
        blocks.append(f"{_head(index, chunk)}\n{body}")
    return (f"You are a senior engineer giving a complete code walkthrough that "
            f"answers the developer's query. Cover the ENTIRE relevant flow end "
            f"to end — do not stop early, do not leave a thread dangling.\n\n"
            f"STRICT RULES:\n{RULES}\n\nQUERY: {question}\n"
            f"{_context(context)}\n"
            f"RETRIEVED CHUNKS:\n\n" + "\n".join(blocks))


def _context(context: str) -> str:
    """A previous walkthrough, marked NON-CITABLE in the strongest terms.

    Without that line the model cites it, the splicer finds no chunk behind the
    citation, and the block silently disappears from the answer.
    """
    if not context.strip():
        return ""
    return ("\nCONTEXT — a previous walkthrough over the SAME code. Use it to "
            "know what matters and in what order. It is NOT citable: every "
            "line of code must still come from a numbered chunk below.\n\n"
            f"{context}\n")


def _head(index: int, chunk: ChunkMeta) -> str:
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
