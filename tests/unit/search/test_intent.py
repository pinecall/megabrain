"""What the QUESTION is asking for, and the punishments that ignore it.

FOUND IN USE on sinatra, and it is the worst ranking failure measured so far.
For "where are the tests for halt?" the chunk holding the four canonical halt
tests is the **best match in the entire repository** by raw cosine — rank #0 of
2 700 chunks. The pipeline delivered it at **#115**, so it never entered the
bundle at all and two agents had to fall back to grep.

Decomposed, lane by lane:

    cosine crudo (what indexing found)   #0
    pipeline as shipped                  #115
    without test_penalty                 #2
    without file_fusion                  #83
    without either                       #0

The test penalty did it. It exists for a good reason — tests quote the
implementation's vocabulary by design, so they match nearly every query ABOUT
an implementation — but it was applied blind: a query that says the word
"tests" gets its answer down-weighted for being a test.

So the penalty learns to read the question, and the recall floor stops
excluding tests when tests are what was asked for. One signal, two users.
"""

from __future__ import annotations

import pytest

from megabrain.search.intent import wants_tests

ASKS_FOR_TESTS = [
    "where are the tests for halt?",
    "which test covers the retry backoff",
    "show me the specs for the parser",
    "what tests pin this behaviour",
    "unit tests for the session store",
    "where is this behaviour tested",
    "test coverage for the auth middleware",
]

ASKS_FOR_IMPLEMENTATION = [
    "how does halt interrupt the request",
    "where is the retry backoff computed",
    "how are before and after filters registered",
    "what does the parser do with a malformed token",
    # The trap: a query about the code that RUNS tests is not a query for the
    # tests themselves — and this is the phrasing most likely to fool a
    # keyword rule, which is exactly why it is pinned here.
    "how does the test runner discover and load test files",
]


@pytest.mark.parametrize("query", ASKS_FOR_TESTS)
def test_a_question_about_TESTS_is_recognised(query: str) -> None:
    assert wants_tests(query) is True


@pytest.mark.parametrize("query", ASKS_FOR_IMPLEMENTATION)
def test_a_question_about_the_IMPLEMENTATION_is_not(query: str) -> None:
    assert wants_tests(query) is False


def test_the_signal_is_deterministic_and_model_free() -> None:
    """It runs on the query path of every search. A model call here would put a
    network round trip in front of a 4 ms answer, and a non-deterministic one
    would make the same question rank differently between runs — which is the
    property the whole engine is built to keep."""
    assert wants_tests("where are the tests") == wants_tests("where are the tests")


def test_the_penalty_STANDS_DOWN_when_tests_are_what_was_asked_for(tmp_path) -> None:
    """The measured failure, as a unit: the penalty must not fire on a query
    that asked for tests."""
    from megabrain.search.scoring.context import build_context
    from megabrain.search.scoring.lanes import TestPenalty
    from tests.unit.search.factories import small_index

    state = small_index(tmp_path)
    with state:
        def ctx_for(query: str):
            return build_context(query=query, params=state.params, metas=state.metas,
                                 chunks=state.chunks, file_paths=state.file_paths,
                                 files=state.files,
                                 query_vector=state.embedder.embed([query])[0])

        assert TestPenalty().applies(ctx_for("how does the service handle a request"))
        assert not TestPenalty().applies(ctx_for("where are the tests for handle"))


def test_the_recall_floor_ADMITS_a_test_when_tests_were_asked_for(tmp_path) -> None:
    """The floor's job is that a ranking opinion cannot become a recall gate.
    It excluded tests unconditionally — which turned the one query where a test
    IS the answer into the one query the floor could not rescue.
    """
    import numpy as np

    from megabrain.search.bundle.floors import file_floor
    from megabrain.storage import Store
    from megabrain.storage.model import ChunkMeta

    with Store(tmp_path) as store:
        store.files.upsert("svc.py", "sha", "class Service", None)
        store.files.upsert("tests/test_svc.py", "sha", "def test_handle", None)
    metas = [ChunkMeta(id=1, file="svc.py", kind="class", name="Service",
                       part=None, start_line=1, end_line=5, text="class Service: pass",
                       breadcrumb="svc.py"),
             ChunkMeta(id=2, file="tests/test_svc.py", kind="function",
                       name="test_handle", part=None, start_line=1, end_line=5,
                       text="def test_handle(): pass", breadcrumb="tests/test_svc.py")]
    chunks = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    wanted = np.array([1.0, 0.0], dtype=np.float32)      # nearest: the TEST chunk

    for query, admitted in (("how does Service handle a request", False),
                            ("where are the tests for handle", True)):
        owed = file_floor(metas=metas, all_metas=metas, all_chunks=chunks,
                          query_vector=wanted, already=set(), params=state_params(),
                          query=query)
        assert ("tests/test_svc.py" in owed) is admitted, query


def state_params():
    from megabrain.search.params import DEFAULT_PARAMS
    return DEFAULT_PARAMS
