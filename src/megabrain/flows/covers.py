"""Does the cached question already ask for everything the query asks for?

Cosine cannot answer this, and the reason is structural: cosine is SYMMETRIC
while "covers" is not. A compound question that CONTAINS a cached one scores
~1.0 against it and gets served an answer to half of what was asked.

Reported live: "How do before and after filters run around a handler, and how
is a route defined?" was served the cached FILTERS walkthrough alone, and the
routing half vanished with no sign that anything had been dropped.

So the serve lane needs this asymmetric check on top of the score: nearly every
content word of the QUERY must already appear in the cached question. New
content words mean the caller is asking for more than the cache holds, and the
right move is to attach the flow as context and narrate fresh.
"""

from __future__ import annotations

import re

__all__ = ["covers", "content_words", "COVERAGE"]

COVERAGE = 0.8
"""Share of the query's content words the cached question must contain.

Not 1.0: a paraphrase legitimately introduces a word or two ("stop the bot from
talking" for "cancel TTS"), and demanding every word would turn the cache off
for exactly the rephrasings it exists to catch.
"""

# Question scaffolding carries no topic: "how does X work" and "where is X
# handled" ask the same thing about X. Only the CONTENT words decide. The
# non-English rows exist because an ASCII-era version counted `cómo` and `el`
# as topic, and no Spanish paraphrase could ever reach the coverage bar.
STOP = frozenset("""a an and are as at be been but by can do does doing done for
from get gets had has have how i if in into is it its of on or our so than that
the their then there these they this to under up upon was were what when where
which while who why will with would you your
cómo como dónde donde qué cuál quién cuándo el la los las un una unos unas de
del en es son está están para por con se al lo su sus y o funciona hace
onde quem quando um uma os das dos no na em não com sem seu sua
comment où pourquoi quel quelle qui quand le les des du au aux est sont dans
pour sur ce cette il elle ne pas que
wie wo warum was welche wer wann der die das den dem ein eine einen einer ist
sind für mit von auf im am und oder nicht""".split())

_WORD = re.compile(r"[^\W\s]+", re.UNICODE)


def content_words(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower())
            if word not in STOP and len(word) > 1}


def covers(question: str, cached_question: str) -> bool:
    """True when `cached_question` asks for everything `question` asks for."""
    asked = content_words(question)
    if not asked:
        return True
    return len(asked & content_words(cached_question)) / len(asked) >= COVERAGE
