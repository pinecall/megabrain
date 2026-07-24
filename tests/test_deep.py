"""The deep retriever (retrieval/deep.py) — the internal agent that
assembles the package the outer agent would otherwise hunt for.

Pins the CONTRACT with a scripted chat: tools execute deterministically,
`add` specs are validated against disk, bodies resolve at prune time with
dedup against already-rendered chunks, and every failure fails open."""

import json
from types import SimpleNamespace

from megabrain.retrieval import deep


def _scripted(replies):
    it = iter(replies)

    def chat(model, prompt, max_tokens, timeout=0):
        return next(it)
    return chat


def _fake_lane(monkeypatch, replies):
    monkeypatch.setattr(
        "megabrain.retrieval.rerank.judge_lane",
        lambda model=None: (_scripted(replies), "scripted", True))


def test_retriever_adds_validated_specs_and_stops_on_done(tiny_repo, monkeypatch):
    _fake_lane(monkeypatch, [
        json.dumps({"actions": [
            {"tool": "grep", "pattern": "check_password"},
            {"tool": "add", "specs": ["auth/login.py#check_password",
                                      "does/not/exist.py"]}],
            "done": False}),
        json.dumps({"actions": [], "done": True}),
    ])
    res = {"chunks": []}
    rec = deep.deep_retrieve(SimpleNamespace(), tiny_repo,
                             "how is a login password checked", res)
    assert rec and rec["done"] and rec["turns"] == 2
    assert rec["specs"] == ["auth/login.py#check_password"]  # invalid dropped
    assert res["deep"]["blocks"]                              # body resolved
    assert any("hash(password)" in ln
               for b in res["deep"]["blocks"] for ln in b["lines"])


def test_specs_covered_by_rendered_chunks_are_not_paid_twice(tiny_repo, monkeypatch):
    _fake_lane(monkeypatch, [
        json.dumps({"actions": [{"tool": "add",
                                 "specs": ["billing/invoice.py:1-2"]}],
                    "done": True}),
    ])
    res = {"chunks": [{"id": 9, "file": "billing/invoice.py",
                       "start_line": 1, "end_line": 40,
                       "text": "def create_invoice(): ..."}]}
    rec = deep.deep_retrieve(SimpleNamespace(), tiny_repo, "q", res)
    assert rec and rec["specs"] == ["billing/invoice.py:1-2"]
    assert rec["blocks"] == []          # span already rendered as a body


def test_garbage_reply_fails_open(tiny_repo, monkeypatch):
    _fake_lane(monkeypatch, ["sorry, I cannot help with that"])
    res = {"chunks": []}
    assert deep.deep_retrieve(SimpleNamespace(), tiny_repo, "q", res) is None
    assert "deep" not in res


def test_dead_lane_fails_open(monkeypatch):
    def broken(model=None):
        raise TimeoutError("lane down")
    monkeypatch.setattr("megabrain.retrieval.rerank.judge_lane", broken)
    res = {"chunks": []}
    assert deep.deep_retrieve(SimpleNamespace(), "/tmp", "q", res) is None
