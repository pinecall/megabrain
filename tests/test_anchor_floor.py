"""The chunk-level lexical anchor floor (bundle._anchor_chunks).

Field case (attrs#1549): file fusion near-ties every chunk of a monolithic
file, tier1_chunk_cap cuts an arbitrary top-N of a flat distribution, and the
capture site `_CountingAttr.default` — holding the query's own rare identifier
`takes_self` — fell at in-file rank 16 of 27 (0.990 vs 1.148 top). No score
lane could rescue a CHUNK; what discriminates it is lexical. The floor grants
a signal slot to chunks holding a rare multiword identifier the query quoted:
deterministic, no LLM, pure additions — the recall-floor doctrine one level
down."""

from types import SimpleNamespace

import numpy as np

from megabrain.retrieval.bundle import _anchor_chunks, selection
from megabrain.retrieval.params import DEFAULT_PARAMS


def _meta(file, text):
    return SimpleNamespace(file=file, text=text)


def _metas_fused(rows):
    metas = [_meta(f, t) for f, t, _ in rows]
    fused = np.array([s for _, _, s in rows])
    return metas, fused


def test_rare_quoted_identifier_earns_its_chunk_a_slot():
    metas, fused = _metas_fused([
        ("src/core.py", "def unrelated(): pass", 1.10),
        ("src/core.py", "self._default = Factory(meth, takes_self=True)", 0.99),
        ("src/other.py", "x = 1", 0.50),
    ])
    hits = _anchor_chunks("where takes_self captures the method", metas, fused,
                          DEFAULT_PARAMS)
    assert hits == {1: ["takes_self"]}


def test_common_identifier_is_not_an_anchor():
    # __init__ appears everywhere — df above the cap means it discriminates
    # nothing and grants nothing
    rows = [("src/f%d.py" % i, "def __init__(self): pass", 0.9)
            for i in range(DEFAULT_PARAMS.anchor_df_cap + 1)]
    metas, fused = _metas_fused(rows)
    assert _anchor_chunks("the __init__ path", metas, fused,
                          DEFAULT_PARAMS) == {}


def test_single_common_words_never_anchor():
    # only multiword identifiers (snake_case / camelCase) qualify — prose
    # words like "default" or "captured" are not quoted names
    metas, fused = _metas_fused([("src/a.py", "default captured value", 1.0)])
    assert _anchor_chunks("default captured", metas, fused,
                          DEFAULT_PARAMS) == {}


def test_tests_and_demos_neither_count_nor_win_slots():
    # tests/demos quote implementation identifiers BY DESIGN (attrs field
    # case: takes_self df=11 with tests, 5 without — one over the cap) and
    # they already have their own sections
    rows = [("src/impl.py", "uses takes_self here", 0.9)]
    rows += [("tests/test_%d.py" % i, "asserts takes_self", 0.8)
             for i in range(DEFAULT_PARAMS.anchor_df_cap + 2)]
    rows += [("examples/demo.py", "demo takes_self", 0.7)]
    metas, fused = _metas_fused(rows)
    hits = _anchor_chunks("check takes_self flow", metas, fused,
                          DEFAULT_PARAMS)
    assert list(hits) == [0]                      # impl chunk only


def test_additions_are_capped_and_ranked_by_anchor_count_then_score():
    rows = [("src/m%d.py" % i, "rare_name_a here", 0.5 + i / 100)
            for i in range(DEFAULT_PARAMS.anchor_chunk_cap + 3)]
    rows.append(("src/both.py", "rare_name_a and rare_name_b", 0.1))
    metas, fused = _metas_fused(rows)
    hits = _anchor_chunks("rare_name_a rare_name_b", metas, fused,
                          DEFAULT_PARAMS)
    assert len(hits) == DEFAULT_PARAMS.anchor_chunk_cap
    assert next(iter(hits)) == len(rows) - 1      # 2 anchors outranks score


def test_selection_appends_anchor_chunks_as_pure_additions():
    res = {
        "tier1": [{"chunks": [{"id": 1, "score": 1.0}]}],
        "tier2": [{"score": 0.8, "best_chunk": {"id": 2}}],
        "anchors": [{"id": 3, "score": 0.6, "anchors": ["takes_self"]},
                    {"id": 1, "score": 1.0, "anchors": ["dup"]}],  # deduped
    }
    picked = selection(res)
    assert [c["id"] for c, _ in picked] == [1, 2, 3]
    assert picked[2][0]["anchors"] == ["takes_self"]
