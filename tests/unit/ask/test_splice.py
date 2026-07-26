"""The splice: the model cites, the engine pastes the real bytes.

This is the anti-hallucination guarantee and the reason `ask` is not a chatbot.
The model is never allowed to write code — it emits `[[3]]` or `[[3:705-731]]`
and every line that reaches the reader comes verbatim from the index.

Invariant #5 lives here: feed the narrator a response full of fabricated code
and assert none of it survives.
"""

from __future__ import annotations

import pytest

from megabrain.ask.citing.citations import Citation, parse_citations
from megabrain.ask.citing.splice import SPLICE_CAP, splice
from megabrain.storage.model import ChunkMeta


def chunk(index: int, text: str, *, file: str = "svc.py", start: int = 1,
          name: str | None = "handle") -> ChunkMeta:
    return ChunkMeta(id=index, file=file, kind="function", name=name, part=None,
                     start_line=start, end_line=start + text.count("\n"),
                     text=text, breadcrumb=f"{file}::{name}")


CANDIDATES = [
    chunk(0, "def handle(request):\n    return run(request)\n"),
    chunk(1, "def run(request):\n    check(request)\n    return request\n",
          file="util.py", start=10, name="run"),
]


# ---- the grammar ------------------------------------------------------------


@pytest.mark.parametrize(("text", "expected"), [
    ("see [[0]]", [Citation(0, ())]),
    ("see [[1:10-12]]", [Citation(1, ((10, 12),))]),
    ("see [[1:L10-L12]]", [Citation(1, ((10, 12),))]),      # models mirror the header
    ("see [[1: 10 - 12 ]]", [Citation(1, ((10, 12),))]),    # stray spaces
    ("see [[1:10-11, 12-12]]", [Citation(1, ((10, 11), (12, 12)))]),
    ("see [[1:11]]", [Citation(1, ((11, 11),))]),           # a POINT citation
])
def test_every_spelling_the_models_actually_use(text: str,
                                                expected: list[Citation]) -> None:
    """Each of these came from a real transcript. An unmatched citation leaks
    into the answer as raw `[[k:line]]` litter where the evidence should be —
    one run cited almost exclusively in point form and rendered nothing."""
    assert parse_citations(text) == expected


def test_single_brackets_stay_prose() -> None:
    """Double brackets exist so the model can still write [1] in prose without
    it being read as a citation."""
    assert parse_citations("as noted in [1] and [2]") == []


# ---- the splice itself ------------------------------------------------------


def test_a_whole_chunk_citation_pastes_the_chunk_verbatim() -> None:
    out = splice("look: [[0]]", CANDIDATES)
    assert "def handle(request):" in out
    assert "    return run(request)" in out


def test_a_range_citation_pastes_only_those_lines() -> None:
    wide = [chunk(0, "\n".join(f"line_{n}" for n in range(40)), start=1)]
    out = splice("look: [[0:10-12]]", wide)
    assert "line_9" in out and "line_11" in out
    assert "line_20" not in out


def test_a_single_line_citation_widens_to_a_window() -> None:
    """Deliberate: one naked line explains nothing, and a model citing a
    single line is pointing at a PLACE, not quoting a statement."""
    wide = [chunk(0, "\n".join(f"line_{n}" for n in range(40)), start=1)]
    out = splice("look: [[0:20]]", wide)
    assert "line_19" in out
    assert out.count("\n") > 6, "a single line was pasted alone"


def test_the_spliced_block_names_its_file_and_lines() -> None:
    """A block a reader cannot locate is a quote, not evidence."""
    out = splice("look: [[1:10-12]]", CANDIDATES)
    assert "util.py" in out and "L10-12" in out


def test_MODEL_WRITTEN_CODE_NEVER_REACHES_THE_OUTPUT() -> None:
    """Invariant #5. The model wrote a plausible function that does not exist
    in this repository; the reader must not see one line of it."""
    fabricated = (
        "Here is the code:\n\n```python\n"
        "def handle(request):\n    return DROP_TABLE(request)  # invented\n"
        "```\n\nand the real one is [[0]]\n")
    out = splice(fabricated, CANDIDATES)
    assert "DROP_TABLE" not in out
    assert "invented" not in out
    assert "return run(request)" in out, "the cited code should still be there"


def test_prose_survives_untouched() -> None:
    out = splice("The handler delegates. [[0]] Then it returns.", CANDIDATES)
    assert "The handler delegates." in out and "Then it returns." in out


def test_a_citation_of_a_chunk_that_does_not_exist_is_dropped_not_printed() -> None:
    """Better a missing block than `[[99]]` in the middle of a sentence."""
    out = splice("see [[99]]", CANDIDATES)
    assert "[[99]]" not in out


def test_the_same_span_is_not_pasted_twice() -> None:
    """Models cite their own evidence again when summarising, and the reader
    scrolls the same forty lines a second time."""
    out = splice("[[0]] … and again [[0]]", CANDIDATES)
    assert out.count("def handle(request):") == 1


def test_a_huge_whole_chunk_citation_narrows_to_the_cited_symbol() -> None:
    """The prompt asks the model to sub-range a big chunk; when it does not,
    the reader eats the whole file for a two-line claim. The net is
    deterministic, prompt compliance is not."""
    body = "\n".join(f"    line_{n} = {n}" for n in range(SPLICE_CAP + 40))
    big = [chunk(0, f"def enormous():\n{body}\n", name="enormous")]
    out = splice("see [[0]]", big)
    assert out.count("\n") < SPLICE_CAP + 20, "the whole chunk was pasted"
