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

# ~50K tokens of candidate code, which fits every default cloud model. A local
# runtime has a smaller window and will TRUNCATE the prompt silently, so it is
# overridable rather than baked in.
MAX_CTX_CHARS = int(os.environ.get("MEGABRAIN_ASK_CTX_CHARS", "200000"))

RULES = """\
- You may NOT write code. Cite it: [[k]] for a whole chunk, [[k:lo-hi]] for a
  range, [[k:lo-hi, lo2-hi2]] for several. The engine replaces each citation
  with the real lines from disk. Code you type is DELETED before the reader
  sees it, so a walkthrough without citations has no code in it.
- Cite GENEROUSLY and COMPLETELY: prefer a whole [[k]] so the reader sees the
  full implementation. Sub-range only a very large chunk, and then take the
  whole enclosing function, not a few lines. Never cite the same span twice.
- Narrate the code's ACTUAL runtime behaviour, traced mechanically from the
  cited lines in execution order: what runs first, what state each step reads
  and writes, in what order. NEVER present a name, a docstring, a comment or an
  apparent intention as behaviour — on buggy code, what the lines do is not
  what they meant. If two cited spans interact, say which runs first and what
  value the reader sees at that point.
- If the query reports a bug or unexpected behaviour, treat that report as
  FACT and walk the execution order until it explains how the cited code
  produces exactly that. If the cited code cannot produce it, say so
  explicitly — never conclude the code is fine because it looks like it should
  be."""


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
