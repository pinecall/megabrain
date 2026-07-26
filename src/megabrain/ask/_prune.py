"""Dropping a section that says nothing once its quotes have been deduplicated.

A REGRESSION this engine introduced, reported by both readers of the same round
in the same words. Quoting a repeated range as "— quoted above" was a win of
~60 duplicated lines; but when EVERY citation in a section is a repeat, the
section survives as a heading over a list of back-references:

  "The 'Pattern to follow' section is pure noise — it lists the same two spans
   already rendered above it and says 'quoted above' for each. Zero information,
   and it re-costs the reader's attention at exactly the point they're deciding
   what to write."

A section whose every quote was already shown is not a shorter section. It is a
section with nothing in it, and a heading is a promise the reader has to spend
attention to find empty.
"""

from __future__ import annotations

import re

__all__ = ["prune_empty_sections"]

_SPLIT = re.compile(r"(?=^## )", re.MULTILINE)
_BACKREF = re.compile(r"—\s*quoted above\s*$", re.MULTILINE)


def prune_empty_sections(text: str) -> str:
    """Remove `## ` sections whose only content is back-references.

    Runs AFTER quoting, on the rendered text: whether a section still carries
    code is a fact about the render, not about the citations that produced it —
    the same range can be new in one answer and a repeat in the next.
    """
    return "".join(part for part in _SPLIT.split(text) if not _is_hollow(part))


def _is_hollow(section: str) -> bool:
    """Whether EVERY line of content under the heading is a back-reference.

    Every line, so the two things that make a section worth keeping both save
    it: a fenced block (it quoted something new) and any line of prose (the
    APPLY marker and the specification of the change live under an anchor's
    heading, and dropping those would delete the instruction).
    """
    if not section.startswith("## ") or "```" in section:
        return False
    body = [line for line in section.split("\n")[1:] if line.strip()]
    return bool(body) and all(_BACKREF.search(line) for line in body)
