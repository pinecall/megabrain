"""One sub-agent's turn.

Apart from the orchestration because it is the part that must obey the SAME
guarantee as the narrator: a sub-agent allowed to paste code is the identical
hole, one level down and harder to see.
"""

from __future__ import annotations

from ..providers.chat import ChatProvider
from ..storage.model import ChunkMeta
from .prompt import RULES, build_prompt
from .splice import splice

__all__ = ["answer_part"]

MAX_TOKENS = 1600


def answer_part(provider: ChatProvider, sub_query: str,
                chunks: list[ChunkMeta]) -> str:
    """Ask about one part, splice the citations, return markdown."""
    answer = provider.stream_chat({
        "model": getattr(provider, "model", ""), "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "messages": [{"role": "user", "content": _prompt(sub_query, chunks)}]})
    return splice(answer.text, chunks)


def _prompt(sub_query: str, chunks: list[ChunkMeta]) -> str:
    """The same cite-only rules, scoped to one part of the question.

    The chunk block is reused from `build_prompt` rather than re-numbered here:
    the absolute line numbers are what make `[[k:lo-hi]]` land on the right
    lines, and a second implementation of that is a second chance to get the
    offset wrong.
    """
    numbered = build_prompt("", chunks).split("RETRIEVED CHUNKS:\n\n", 1)[-1]
    return (f"You are one of several engineers answering part of a larger "
            f"question.\n\nYOUR PART: {sub_query}\n\nSTRICT RULES:\n{RULES}\n\n"
            f"RETRIEVED CHUNKS:\n\n{numbered}")
