"""What the expander asks for.

Its own module for the same reason the judge's prompt is: the wording IS the
behaviour. Its load-bearing clause was written against an observed failure —
the model naming FILES, which it cannot know and duly hallucinated
(`test/main_test.rb`, in a repository whose tests are named otherwise). It is
asked for identifiers because an identifier is a thing the symbol table can
verify, and a path is a thing only the model believes.

What is done with the answers is `_echo.py`: telling and believing are
different jobs.
"""

from __future__ import annotations

from typing import Any

from ._echo import MAX_TERMS

__all__ = ["prompt_for", "listing", "MAX_LISTED", "MAX_TOKENS"]

MAX_TOKENS = 200
"""The reply is a short JSON array of names. Room to finish it, not room to
explain it — the prompt asks for ONLY the array, and a budget that fits an
essay is an invitation to write one."""

MAX_LISTED = 25
"""Files shown to the namer. It needs to see the SHAPE of what was found to
name what is missing; it does not need the tail of a ranked list to do it."""

PROMPT = """An engineer searched a codebase for:

{question}

The search returned these files:
{listing}

Name the IDENTIFIERS that would find what this search MISSED — the method, \
class, constant or module name the code itself would use, which the question \
did not say. Think about what the found files reference but do not contain.

Rules: return identifiers as they appear IN THE CODE, never file paths or \
directory names — you cannot know how this project names its files. Do not \
repeat words already in the question or in the file names above. If the search \
looks complete, return an empty array.

Return ONLY a JSON array of at most {most} strings. Example: ["invoke", \
"ThrowSymbol"]"""


def prompt_for(question: str, found: list[Any]) -> str:
    """The whole ask, assembled here because this module owns its placeholders.

    The caller supplies a question and a pool; how many terms are wanted and
    how much of the pool is worth showing are this module's business, and a
    caller that had to know them could set one and forget the other.
    """
    return PROMPT.format(question=question, listing=listing(found), most=MAX_TERMS)


def listing(found: list[Any]) -> str:
    """The pool as the namer sees it: paths, and the symbols each one declares.

    Symbols and not bodies. The namer's job is to notice what is REFERENCED but
    absent, and a declaration list shows that at a fraction of the tokens — a
    round that costs as much as the answer is a round nobody leaves on.
    """
    lines = []
    for entry in found[:MAX_LISTED]:
        names = [s.get("name", "") for s in (entry.get("symbols") or [])][:6]
        suffix = f"  ({', '.join(n for n in names if n)})" if names else ""
        lines.append(f"- {entry['file']}{suffix}")
    return "\n".join(lines) or "- (nothing)"


