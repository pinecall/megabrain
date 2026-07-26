"""When the answer ADMITS a body is missing, serve it and let it write again.

MEASURED on sinatra. Asked when before filters run, the answer said `dispatch!`
was "not shown in the provided chunks, though its behavior is implied by the
flow" — and then hedged about behaviour the code states outright, saying after
filters "may or may not run" when `dispatch!` puts them in an `ensure`, so they
always do. The engine could resolve that body; the widening did quote it; but
the widening runs AFTER the model writes, so the prose above never benefited.

The alternative was measured and rejected: handing every called-but-unshown
definition up front is 159 bodies on sinatra, 134 on the SDK, 102 on click —
straight back to the context size that stopped the narrator opening anything.

So the trigger is the admission itself, which is rare and unambiguous: 1 of 14
real answers, no false positives in the other 13. `OPENING` already forbids the
sentence, which is what makes it a reliable signal that something went wrong.
"""

from __future__ import annotations

from megabrain.ask.converse._admits import admitted_gap

CONFESSIONS = [
    "`dispatch!` is not shown in the provided chunks, though its behavior is implied",
    "the body of `resolve` is not included in the retrieved context",
    "`handle` isn't shown above, so this is inferred",
    "The implementation of `run` is not present in the chunks provided",
]


def test_each_measured_confession_is_detected() -> None:
    """All four spellings came from real answers or their near neighbours. A
    rule that only catches the exact one measured catches nothing next time."""
    for text in CONFESSIONS:
        assert admitted_gap(text), f"missed: {text}"


def test_an_ordinary_answer_admits_nothing() -> None:
    """The 13 of 14 that must stay free: no second call, no delay, no rewrite."""
    for text in ["The guard belongs before `mkdir`, which creates the parents.",
                 "`content_type` returns early unless a type is given.",
                 "This is not the behaviour the comment claims.",
                 "The chunks show the whole flow end to end."]:
        assert not admitted_gap(text), f"false positive: {text}"


def test_the_admission_must_be_about_MISSING_code() -> None:
    """"not shown" is the load-bearing phrase. A sentence that merely contains
    "shown" or "provided" is ordinary prose."""
    assert not admitted_gap("as shown above, the retry is capped")
    assert not admitted_gap("the provided path is validated first")
