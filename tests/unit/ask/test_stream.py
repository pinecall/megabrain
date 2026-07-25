"""Splicing a live stream, one delta at a time.

The failure this prevents is unrecoverable by nature: text already printed to a
terminal or a browser cannot be un-printed. A citation cut across a delta
boundary must never be flushed as prose.
"""

from __future__ import annotations

from megabrain.ask.stream import Splicer
from tests.unit.ask.test_splice import CANDIDATES


def drive(*deltas: str) -> str:
    """Feed the deltas exactly as they would arrive."""
    splicer = Splicer(CANDIDATES)
    return "".join(splicer.feed(delta) for delta in deltas) + splicer.flush()


def test_prose_flushes_immediately() -> None:
    """The point of streaming: a reader watching an answer appear."""
    splicer = Splicer(CANDIDATES)
    assert splicer.feed("The handler ") == "The handler "


def test_a_citation_split_across_deltas_is_never_emitted_raw() -> None:
    """`[[0` arrives, then `]]`. Printed as prose in between, it is on screen
    for good."""
    splicer = Splicer(CANDIDATES)
    partial = splicer.feed("see [[")
    assert "[[" not in partial

    finished = splicer.feed("0]] done")
    assert "def handle(request):" in finished
    assert "[[0]]" not in finished


def test_the_whole_answer_survives_however_it_is_chopped() -> None:
    """Same text, three chunkings, one result — because a delta boundary is
    an accident of the network, not of the answer."""
    whole = drive("The handler is [[0]] and that is all.")
    in_pieces = drive("The handler", " is [[", "0", "]] and", " that is all.")
    letter_by_letter = drive(*"The handler is [[0]] and that is all.")
    assert whole == in_pieces == letter_by_letter
    assert "def handle(request):" in whole


def test_a_fabricated_fence_split_across_deltas_still_never_lands() -> None:
    """Invariant #5 under streaming: half a fence must not sail through as
    prose while the engine waits for the other half."""
    out = drive("look:\n```py", "thon\ndef fake():\n    DROP", "_TABLE()\n```\nreal: [[0]]")
    assert "DROP_TABLE" not in out
    assert "def fake" not in out
    assert "def handle(request):" in out


def test_an_unfinished_citation_at_the_end_leaves_no_litter() -> None:
    """The stream died mid-citation. A missing block is acceptable; `[[0:` in
    the middle of a sentence is not."""
    out = drive("the code is [[0:")
    assert "[[" not in out


def test_nothing_is_lost_when_the_stream_ends_cleanly() -> None:
    out = drive("first ", "second ", "third")
    assert out == "first second third"


def test_a_fence_that_never_closes_is_dropped_at_flush() -> None:
    """The stream died part-way through code the model invented. `splice`
    only removes fences that CLOSE, so this is the one case where fabricated
    code could reach a reader — invariant #5 failing where nobody looks."""
    out = drive("look:\n```python\ndef fake():\n    DROP_TABLE()")
    assert "DROP_TABLE" not in out
    assert "def fake" not in out


def test_a_GROUPED_citation_split_at_the_comma_never_leaks() -> None:
    """The grammar accepts [[1:173-240], [2:241-307]] — but the stream holder
    predated it. Split at the comma, `[[0:1-2], ` flushed as prose and the
    second half arrived as litter: the exact reported failure, resurrected one
    layer down. A delta boundary is an accident of the network; it must not be
    able to change what the reader sees.
    """
    whole = drive("the fallback [[0]] handles it")
    del whole  # the fixture chunks are small; what matters is the split below

    whole_text = "the fallback [[0:1-2], [1:10-11]] handles it"
    out = drive("the fallback [[0:1-2], ", "[1:10-11]] handles it")
    assert "[[0:1-2]" not in out and "[1:10-11]" not in out
    assert out == drive(whole_text) == drive(*whole_text), \
        "the partition changed the rendered answer"


def test_a_stream_dying_MID_GROUP_leaves_no_litter() -> None:
    out = drive("see [[0:1-2], [1:10")
    assert "[[" not in out and "[1:10" not in out
