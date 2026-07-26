"""Did the answer admit it was writing without a body it needed?

MEASURED on sinatra: "`dispatch!` is not shown in the provided chunks, though
its behavior is implied by the flow" — followed by a hedge about behaviour the
code states outright. The engine could resolve that body, and the widening did
quote it, but the widening runs after the model writes, so the prose never
benefited.

Handing every called-but-unshown definition up front was measured and rejected:
159 bodies on sinatra, 134 on the SDK, 102 on click — straight back to the
context size that stopped the narrator opening anything at all.

So the admission is the trigger, and it earns that job by being rare and
unambiguous — 1 of 14 real answers, no false positives in the other 13.
`OPENING` already forbids the sentence in so many words, which is exactly why
its presence is evidence that something went wrong rather than ordinary prose.
"""

from __future__ import annotations

import re

__all__ = ["admitted_gap"]

_ADMISSION = re.compile(
    r"\b(?:is|are|isn't|aren't|was|were|not)\b[^.\n]{0,40}?"
    r"\b(?:not\s+)?(?:shown|included|present|available|provided)\b"
    r"[^.\n]{0,60}?\b(?:chunk|chunks|context|above|provided)\b",
    re.IGNORECASE)
"""One sentence claiming code was unavailable, in the spellings measured.

Deliberately narrow: it must pair a negation with BOTH a "shown/included/
present" word and a "chunks/context" word, because "as shown above" and "the
provided path" are ordinary prose that a looser rule flags on every answer."""


def admitted_gap(raw: str) -> bool:
    """Whether `raw` says it lacked code the repository contains."""
    return any(_ADMISSION.search(line) and _negated(line)
               for line in raw.split("\n"))


def _negated(line: str) -> bool:
    """The claim must be that something is NOT there.

    Checked separately from the shape above because the regex allows the
    negation to sit either before the verb ("not shown in the chunks") or after
    it ("is not included above"), and a sentence with no negation at all is
    describing what the reader HAS.
    """
    return bool(re.search(r"\b(?:not|isn't|aren't|never|without|lack\w*)\b",
                          line, re.IGNORECASE))
