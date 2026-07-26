"""The exact text to copy as `find` — short, unique, never elided.

MEASURED, and it is the contract the engine was breaking. `megabrain_replace`
says "copy the anchor from the render, it is verbatim from the index" — but a
quote longer than the cap comes back with `… ‹elided 117 lines› …` in the
middle, so the one string the reader was told to copy is not copyable. The
reader hand-picked a tail slice and took on the uniqueness judgement itself:

  "an elided quote silently breaks the tool's own contract and hands the
   uniqueness judgement back to me — the one step where a mistake costs a
   failed batch plus a Read to recover."

So the wide quote stays (it is what makes the edit CORRECT) and the anchor is
emitted beside it: the minimal slice that occurs exactly once. Cut from the end
the insertion happens at, because that is the seam the reader is aiming for.
"""

from __future__ import annotations

from megabrain.ask._anchors import anchor_blocks
from megabrain.chunkers.model import Chunk
from megabrain.storage import Store

# Longer than MAX_QUOTE_LINES, because an anchor block only exists for a quote
# that had to be elided — that is the contract it repairs. `end` alone is
# ambiguous; the `it` line above it makes the pair unique.
BODY = "\n".join(
    ["describe 'send_file' do", "  setup do", "    @f = 1", "  end"]
    + [f"  it 'case {n}' do\n    assert_equal {n}, {n}\n  end" for n in range(20)]
    + ["  it 'last' do", "    assert_equal 2, 2", "  end", "end"])
LAST = BODY.count("\n") + 1


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    store.files.upsert("test/app_test.rb", "sha", "", None)
    store.chunks.insert([Chunk(file="test/app_test.rb", kind="block", name=None,
                              part=None, start_line=1, end_line=LAST, text=BODY,
                              breadcrumb="t")], None)
    return store


def test_an_insert_after_anchor_is_cut_from_the_END(tmp_path) -> None:
    """The seam of an `insert_after` is the last line, so the slice grows
    upward from it — and it must carry the closing `end`."""
    with repo(tmp_path) as store:
        out = anchor_blocks(store, f"[[test/app_test.rb:1-{LAST}]]\nAPPLY insert_after")
    assert out.rstrip().endswith("end\n```")
    assert "describe 'send_file' do" not in out, "kept the head of a tail anchor"


def test_an_insert_before_anchor_is_cut_from_the_START(tmp_path) -> None:
    """Mirror case: the seam is the first line."""
    with repo(tmp_path) as store:
        out = anchor_blocks(store, f"[[test/app_test.rb:1-{LAST}]]\nAPPLY insert_before")
    assert "describe 'send_file' do" in out


def test_the_anchor_grows_until_it_is_UNIQUE(tmp_path) -> None:
    """A one-line slice of `  end` matches four times — pasted as a `find` the
    whole batch is refused. It grows until exactly one occurrence remains."""
    with repo(tmp_path) as store:
        out = anchor_blocks(store, f"[[test/app_test.rb:1-{LAST - 1}]]\nAPPLY insert_after")
    body = out.split("```")[1]
    assert BODY.count(body.split("\n", 1)[1].rstrip("\n")) == 1


def test_a_SHORT_anchor_is_not_repeated(tmp_path) -> None:
    """The wide quote already IS the copyable string when nothing was elided —
    a second copy is the duplication the readers kept naming as wasted budget."""
    with repo(tmp_path) as store:
        assert anchor_blocks(store, "[[test/app_test.rb:5-7]]\nAPPLY insert_after") == ""


def test_a_citation_with_no_APPLY_is_not_an_anchor(tmp_path) -> None:
    """An example to imitate is not a site being edited."""
    with repo(tmp_path) as store:
        assert anchor_blocks(store, f"see [[test/app_test.rb:1-{LAST}]]") == ""
