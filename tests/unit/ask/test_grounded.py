"""A narrated HOP between two files, checked against the graph the indexer built.

MEASURED on a real repository. Asked about a barge-in mechanism, the narrator
wrote: "`TurnController._handle_barge_in` delegates the actual cleanup to the
session layer by calling `handle_user_interrupted`" — a real function, a real
call site, quoted verbatim from disk. But the two files have ZERO edges between
them, of any kind, either direction; `handle_user_interrupted` has no caller
anywhere in the repository. The graph the indexer already built said so, for
free — the REAL relationship (a different file constructing `TurnController`
with a callback) showed both an import and a call edge.

Consecutive citations, not all pairs: a correct walkthrough of A -> B -> C has
no edge A-C even when every step is right, because the graph only records
DIRECT relations. Checking each hop the narration itself makes — the file just
cited, into the very next one — is the scope that matches what "delegates
to"/"calls" language actually asserts.
"""

from __future__ import annotations

from megabrain.ask.checks.grounded import unlinked_hops
from megabrain.chunkers.model import Chunk
from megabrain.storage import Store


def repo(tmp_path) -> None:
    """Three files: A calls B (a real edge), C is unconnected to either."""
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "c.py"):
            store.files.upsert(path, "sha", "", None)
        store.graph.add_edges("a.py", ["b.py"], "call")


def candidates():
    return [Chunk(file="a.py", kind="function", name="f", part=None,
                  start_line=1, end_line=2, text="", breadcrumb="a.py"),
            Chunk(file="b.py", kind="function", name="g", part=None,
                  start_line=1, end_line=2, text="", breadcrumb="b.py"),
            Chunk(file="c.py", kind="function", name="h", part=None,
                  start_line=1, end_line=2, text="", breadcrumb="c.py")]


def test_a_hop_with_NO_edge_is_flagged(tmp_path) -> None:
    """The measured shape: cite A, then immediately cite an unconnected file."""
    repo(tmp_path)
    out = unlinked_hops("does X [[0]] then Y calls [[2]]", candidates(), tmp_path)
    assert "a.py" in out and "c.py" in out
    assert "graph" in out.lower()


def test_a_hop_the_graph_CONFIRMS_is_silent(tmp_path) -> None:
    """A real edge — the narration is trusted, no note is added."""
    repo(tmp_path)
    assert unlinked_hops("does X [[0]] then calls [[1]]", candidates(), tmp_path) == ""


def test_the_edge_may_run_EITHER_direction(tmp_path) -> None:
    """The graph stores who calls whom; the narration may walk it backwards —
    from the callee up to its caller — and that is still a real relationship."""
    repo(tmp_path)
    assert unlinked_hops("used by [[1]] here, defined in [[0]]",
                        candidates(), tmp_path) == ""


def test_consecutive_citations_of_the_SAME_file_need_no_edge(tmp_path) -> None:
    """Two chunks of one file are not a hop at all."""
    repo(tmp_path)
    with Store(tmp_path) as store:
        store.chunks.insert([Chunk(file="a.py", kind="function", name="f2", part=None,
                                   start_line=3, end_line=4, text="", breadcrumb="a.py")], None)
    cands = candidates() + [Chunk(file="a.py", kind="function", name="f2", part=None,
                                  start_line=3, end_line=4, text="", breadcrumb="a.py")]
    assert unlinked_hops("first [[0]] then [[3]]", cands, tmp_path) == ""


def test_a_PIN_edge_counts_as_a_real_relationship(tmp_path) -> None:
    """A test that pins a file IS a structural fact the indexer recorded — not
    noise, so it must not be flagged either."""
    repo(tmp_path)
    with Store(tmp_path) as store:
        store.files.upsert("test_c.py", "sha", "", None)
        store.graph.add_edges("test_c.py", ["c.py"], "pins")
    cands = candidates() + [Chunk(file="test_c.py", kind="function", name="t", part=None,
                                  start_line=1, end_line=1, text="", breadcrumb="t")]
    assert unlinked_hops("the guard [[2]] is pinned by [[3]]", cands, tmp_path) == ""


def test_an_opened_file_PATH_citation_is_checked_too(tmp_path) -> None:
    """Not only chunk citations — a file opened mid-conversation and cited by
    path is just as much a claimed hop."""
    repo(tmp_path)
    out = unlinked_hops("does X [[0]] then unrelated [[c.py:1-2]]", candidates(), tmp_path)
    assert "c.py" in out


def test_no_citations_means_no_section(tmp_path) -> None:
    repo(tmp_path)
    assert unlinked_hops("plain prose, nothing cited", candidates(), tmp_path) == ""


def test_no_root_means_no_check() -> None:
    """Without a root there is no graph to check against — the multi-agent path
    narrates this way, and this must not error."""
    assert unlinked_hops("does X [[0]] then Y [[2]]", candidates(), None) == ""
