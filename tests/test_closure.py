"""The surface closure loop (retrieval/closure.py) — search v2 for agents.

Pins the CONTRACT, not the LLM: directives resolve deterministically, the
loop is a pure addition, and every failure fails open to the deterministic
result. The LLM calls themselves are mocked — internal-agent quality is
measured by evals/surface in fidelity mode, never by the unit suite."""

from types import SimpleNamespace

import numpy as np
import pytest

from megabrain.retrieval import closure as cl


def _meta(id, file, text, start=1, end=9):
    d = {"id": id, "file": file, "kind": "function", "name": "fn",
         "part": 0, "start_line": start, "end_line": end, "text": text,
         "breadcrumb": ""}
    ns = SimpleNamespace(**d)
    ns.to_dict = lambda d=d: dict(d)
    return ns


class _Store:
    def __init__(self, symbols=()):
        self._symbols = list(symbols)

    def find_symbols(self, name):
        return [s for s in self._symbols if s["name"].endswith(name)]


def _st(metas, symbols=()):
    return SimpleNamespace(store=_Store(symbols))


# ------------------------------------------------------------- _resolve

def test_grep_directive_resolves_rare_terms_only():
    metas = [_meta(1, "src/a.py", "uses takes_self here"),
             _meta(2, "src/b.py", "nothing"),
             _meta(3, "tests/test_a.py", "asserts takes_self")]
    fused = np.array([0.5, 0.4, 0.9])
    out = cl._resolve(_st(metas), metas, fused,
                      {"grep": ["takes_self"]}, have=set())
    # the impl chunk resolves; the test chunk never does (own section)
    assert [(metas[i].file, why) for i, why in out] == \
        [("src/a.py", "grep:takes_self")]


def test_grep_df_cap_rejects_common_terms():
    metas = [_meta(i, f"src/f{i}.py", "common_name x")
             for i in range(cl.GREP_DF_CAP + 1)]
    fused = np.ones(len(metas))
    assert cl._resolve(_st(metas), metas, fused,
                       {"grep": ["common_name"]}, have=set()) == []


def test_symbol_directive_resolves_via_def_site_containment():
    metas = [_meta(1, "src/a.py", "class C: ...", start=10, end=40)]
    fused = np.array([0.5])
    sym = [{"file": "src/a.py", "name": "C.method", "kind": "method",
            "line": 22, "end_line": 30, "signature": ""}]
    out = cl._resolve(_st(metas, sym), metas, fused,
                      {"symbols": ["method"]}, have=set())
    assert [(metas[i].id, why) for i, why in out] == [(1, "symbol:method")]


def test_resolution_is_a_pure_addition_and_deduped():
    metas = [_meta(1, "src/a.py", "rare_term")]
    fused = np.array([0.5])
    # already in the pool -> nothing added
    assert cl._resolve(_st(metas), metas, fused,
                       {"grep": ["rare_term"]}, have={1}) == []


def test_malformed_directives_never_raise():
    metas = [_meta(1, "src/a.py", "x")]
    fused = np.array([0.5])
    out = cl._resolve(_st(metas), metas, fused,
                      {"grep": [None, 42, ""], "symbols": [7],
                       "queries": [None]}, have=set())
    assert out == []


# --------------------------------------------------------- close_surface

def test_close_surface_fails_open_when_the_lane_is_down(monkeypatch):
    def broken(*a, **k):
        raise TimeoutError("lane down")
    monkeypatch.setattr("megabrain.retrieval.rerank.judge_lane", broken)
    res = {"chunks": [{"id": 1}], "kept": 1}
    before = [dict(c) for c in res["chunks"]]
    assert cl.close_surface(SimpleNamespace(), "q", res) is None
    assert res["chunks"] == before          # untouched — the floor holds


def test_budget_caps_internal_calls():
    b = cl._Budget(2)
    assert b.take() and b.take() and not b.take()
    assert b.used == 2


def test_json_of_extracts_and_raises():
    assert cl._json_of('sure! ["a", "b"] done') == ["a", "b"]
    assert cl._json_of('{"closed": true}') == {"closed": True}
    with pytest.raises(ValueError):
        cl._json_of("no json here")
