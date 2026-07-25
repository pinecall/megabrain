"""Rescuing an answer whose citations did not resolve (`_broken` finds them).

The broken fragments — ONLY those — go back to the model with the candidate
list, and it answers with citations. Not the whole answer again: a second
narration costs another full call and comes back with different prose, so the
reader watches the text they were reading get replaced by a different one.

Fail-open means the ANSWER survives, not the broken reference: if the repair
fails, or the model cannot place a fragment, the fragment is DROPPED. A missing
clause is a smaller lie than a path with no code under it.
"""

from __future__ import annotations

import json
import re

_PROMPT = """These references in a code walkthrough could not be resolved. \
Each one names code the writer meant to show but did not cite properly.

Return ONLY a JSON array with one entry per reference, in order, each being \
the correct citation for it — "[[k]]" for a whole chunk or "[[k:lo-hi]]" for a \
range — or "" if no chunk below covers it. No prose, no code.

REFERENCES:
{references}

AVAILABLE CHUNKS:
{chunks}"""

from ..providers.chat import ChatProvider
from ..storage.model import ChunkMeta
from ._broken import broken_references
from .citations import CITATION

__all__ = ["repair", "MAX_TOKENS"]

MAX_TOKENS = 400

# `path.ext` followed by a line range: the shape the model falls back to when
# it forgets it may not write code. The extension is what keeps it from
# matching ordinary inline code like `handle()` or `SSEDecoder`.
_PROSE_REF = re.compile(r"`[^`\n]+\.[A-Za-z0-9]+`\s*L\d+(?:\s*-\s*\d+)?")

# Anything double-bracketed the citation grammar did not accept.
_ANY_BRACKETED = re.compile(r"\[\[[^\]\n]*\]\]")

def repair(answer: str, candidates: list[ChunkMeta],
           provider: ChatProvider) -> str:
    """The answer with broken references replaced by citations, or removed.

    One call for all of them, because they share the candidate list and a call
    per fragment would multiply the cost of a bad answer.
    """
    broken = broken_references(answer)
    if not broken:
        return answer                     # a rescue, not a step
    fixes = _ask_for_citations(broken, candidates, provider)
    for fragment, citation in zip(broken, [*fixes, *([""] * len(broken))]):
        answer = answer.replace(fragment, citation)
    return answer


def _ask_for_citations(broken: list[str], candidates: list[ChunkMeta],
                       provider: ChatProvider) -> list[str]:
    chunks = "\n".join(
        f"[{index}] {chunk.file} L{chunk.start_line}-{chunk.end_line}"
        f"{f' ({chunk.name})' if chunk.name else ''}"
        for index, chunk in enumerate(candidates))
    prompt = _PROMPT.format(references="\n".join(broken), chunks=chunks)
    try:
        reply = provider.chat_text(getattr(provider, "model", ""), prompt,
                                   max_tokens=MAX_TOKENS)
        return _citations_in(reply, len(broken))
    except Exception:                     # noqa: BLE001 — the answer survives
        return []


def _citations_in(reply: str, expected: int) -> list[str]:
    """The JSON array of citations, each validated against the grammar.

    A "fix" that is itself unparseable is worth nothing, and letting it through
    would put new litter where the old litter was.
    """
    found = re.search(r"\[.*\]", reply, re.DOTALL)
    if not found:
        return []
    try:
        parsed = json.loads(found.group(0))
    except ValueError:
        return []
    out = [str(item) if CITATION.fullmatch(str(item).strip()) else ""
           for item in parsed[:expected]]
    return out
