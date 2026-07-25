"""The two decisions a flow cache gets wrong, and how it is stopped.

A cached walkthrough is the most dangerous thing this engine stores: it is
prose ABOUT code, kept apart from the code, and both of the failures below
serve a confident answer that is not wrong-looking at all.

1. A COMPOUND question that CONTAINS a cached one scores ~1.0 against it,
   because cosine is symmetric while "answers everything you asked" is not.
   Field case, reported live: "How do before and after filters run around a
   handler, and how is a route defined?" was served the cached FILTERS
   walkthrough alone, and the routing half vanished without a trace.

2. A flow whose cited FILE CHANGED describes code that no longer exists. It
   must not be served, and it must not survive the next index.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from megabrain.flows import covers, match_flows, serve_verbatim
from megabrain.storage import Store


def vec(*values: float) -> np.ndarray:
    raw = np.array(values, dtype=np.float32)
    return raw / np.linalg.norm(raw)


def write(root: Path, relpath: str, text: str) -> str:
    (root / relpath).parent.mkdir(parents=True, exist_ok=True)
    (root / relpath).write_text(text, encoding="utf-8")
    from megabrain.flows.freshness import sha_of

    return sha_of(root / relpath)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, "filters.py", "def before(): pass\n")
    return tmp_path


def cache(root: Path, question: str, text: str, files: dict[str, str],
          attach: np.ndarray, serve: np.ndarray) -> None:
    with Store(root) as store:
        store.flows.insert(question=question, text=text, files=files,
                           vec=attach, qvec=serve)


# ---- 1. a query that asks for MORE than the cache holds ---------------------


def test_a_compound_question_is_NOT_served_a_half_answer(repo: Path) -> None:
    """The whole reason `covers` exists. The cached question is contained in
    the query, so it scores ~1.0 — and answering it would silently drop
    everything the query asked for beyond it."""
    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do before and after filters run around a handler?",
          "the filters walkthrough", {"filters.py": sha}, vec(1, 0), vec(1, 0))

    with Store(repo) as store:
        metas, attach, serve = store.flows.read_matrix()
    matched = match_flows(metas, attach, serve, vec(1, 0))

    assert matched, "it should still MATCH — it is relevant context"
    assert serve_verbatim(repo, matched,
                          "how do before and after filters run around a handler, "
                          "and how is a route defined?") is None


def test_the_same_question_reworded_IS_served(repo: Path) -> None:
    """The other half: paraphrase is exactly what the cache is for."""
    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do filters run around a handler?", "the walkthrough",
          {"filters.py": sha}, vec(1, 0), vec(1, 0))

    with Store(repo) as store:
        metas, attach, serve = store.flows.read_matrix()
    matched = match_flows(metas, attach, serve, vec(1, 0))

    served = serve_verbatim(repo, matched, "how do filters run around a handler?")
    assert served is not None and served["text"] == "the walkthrough"


@pytest.mark.parametrize(("query", "cached", "covered"), [
    ("how does retry work", "how does retry work", True),
    # "handled" and "work" are content words, so these two questions do NOT
    # cover each other. Conservative on purpose: the cost of being wrong here
    # is serving an answer to a different question.
    ("where is retry handled", "how does retry work", False),
    ("how does retry and backoff work", "how does retry work", False),
    ("how does retry work", "how does retry and backoff work", True),
])
def test_coverage_is_asymmetric(query: str, cached: str, covered: bool) -> None:
    """`covers(query, cached)` asks whether the CACHED question already
    contains everything the query asks for — not whether they are similar."""
    assert covers(query, cached) is covered


# ---- 2. the cited code changed ----------------------------------------------


def test_a_flow_whose_file_CHANGED_is_not_served(repo: Path) -> None:
    """It describes code that no longer exists. Serving it is the worst thing
    this cache can do: confident prose about a function that was rewritten."""
    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do filters run?", "the walkthrough",
          {"filters.py": sha}, vec(1, 0), vec(1, 0))
    write(repo, "filters.py", "def before(): return 'rewritten'\n")

    with Store(repo) as store:
        metas, attach, serve = store.flows.read_matrix()
    matched = match_flows(metas, attach, serve, vec(1, 0))

    assert matched, "it still matches — staleness is checked at SERVE time"
    assert serve_verbatim(repo, matched, "how do filters run?") is None


def test_a_flow_whose_file_VANISHED_is_not_served(repo: Path) -> None:
    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do filters run?", "the walkthrough",
          {"filters.py": sha}, vec(1, 0), vec(1, 0))
    (repo / "filters.py").unlink()

    with Store(repo) as store:
        metas, attach, serve = store.flows.read_matrix()
    assert serve_verbatim(repo, match_flows(metas, attach, serve, vec(1, 0)),
                          "how do filters run?") is None


def test_staleness_is_measured_against_DISK_not_the_index(repo: Path) -> None:
    """Deliberate: the index legitimately lags disk between runs, and a flow
    whose sources are untouched stays valid through that window. Checking the
    index's shas would expire good flows every time anything else changed."""
    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do filters run?", "the walkthrough",
          {"filters.py": sha}, vec(1, 0), vec(1, 0))
    with Store(repo) as store:            # the INDEX says something different
        store.files.upsert("filters.py", "a-completely-different-sha", "", None)

    with Store(repo) as store:
        metas, attach, serve = store.flows.read_matrix()
    served = serve_verbatim(repo, match_flows(metas, attach, serve, vec(1, 0)),
                            "how do filters run?")
    assert served is not None, "disk is unchanged, so the flow is still good"


def test_indexing_PRUNES_a_flow_whose_source_changed(repo: Path) -> None:
    """The second line of defence. Serve-time checks protect the answer;
    pruning stops a stale walkthrough from outliving the code indefinitely."""
    from megabrain.usecases import build_index
    from tests.unit.indexing.fake import CountingEmbedder

    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do filters run?", "the walkthrough",
          {"filters.py": sha}, vec(1, 0), vec(1, 0))
    write(repo, "filters.py", "def before(): return 'rewritten'\n")

    build_index(repo, embedder=CountingEmbedder())

    with Store(repo) as store:
        assert store.flows.read_matrix()[0] == [], "the stale flow survived indexing"


def test_indexing_KEEPS_a_flow_whose_sources_are_untouched(repo: Path) -> None:
    """The other half, and the one that makes the cache worth having."""
    from megabrain.usecases import build_index
    from tests.unit.indexing.fake import CountingEmbedder

    sha = write(repo, "filters.py", "def before(): pass\n")
    cache(repo, "how do filters run?", "the walkthrough",
          {"filters.py": sha}, vec(1, 0), vec(1, 0))

    build_index(repo, embedder=CountingEmbedder())

    with Store(repo) as store:
        assert len(store.flows.read_matrix()[0]) == 1
