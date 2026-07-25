"""The judge lane: a model SELECTS, it never writes.

Same stance as the splice, one level up. The model returns ids; the engine
keeps and reorders its own verbatim chunks. Nothing the model says becomes
content.

The other half of this file is fail-open. The judge is an OPTIMISATION, never
a dependency: no key, a timeout, a malformed reply, an id that does not exist —
every one of them returns the deterministic bundle untouched.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from megabrain.enrich.rerank import RERANK_BATCH, rerank
from megabrain.providers.chat.base import Answer
from tests.unit.ask.test_splice import chunk


class Judge:
    """Replies with whatever the test scripts, per call."""

    model = "judge"
    agent_stream = None

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls = 0
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        return self.stream_chat({"messages": [{"content": prompt}]}).text

    def stream_chat(self, body: dict[str, object], *, on_delta: object = None) -> Answer:
        self.prompts.append(str(body["messages"][0]["content"]))  # type: ignore[index]
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        if reply == "BOOM":
            raise RuntimeError("the judge fell over")
        return Answer(text=reply, finish_reason="stop")


def bundle_of(*files: str) -> dict[str, object]:
    return {
        "query": "how does scoring work", "repo": "r", "ms": 5,
        "tier1": [], "flows": [], "anchors": [],
        "tier2": [{"file": name, "score": 1.0 - index / 100, "via_graph": False,
                   "matched": [], "doc": None, "symbols": [],
                   "best_chunk": asdict(chunk(index, f"def f{index}(): pass\n",
                                              file=name))}
                  for index, name in enumerate(files)],
    }


def test_the_judges_order_becomes_the_order() -> None:
    """The whole point: the engine reorders ITS chunks by the verdict."""
    scored = bundle_of("a.py", "b.py", "c.py")
    out = rerank(scored, Judge("[2, 0, 1]"))          # type: ignore[arg-type]
    assert [entry["file"] for entry in out["tier2"]] == ["c.py", "a.py", "b.py"]


def test_nothing_the_model_writes_becomes_content() -> None:
    """It returns ids. A reply full of prose and fabricated code changes the
    ORDER and nothing else — same stance as the citation splice."""
    scored = bundle_of("a.py", "b.py")
    reply = "Here is better code:\n```python\ndef fake(): DROP_TABLE()\n```\n[1, 0]"
    out = rerank(scored, Judge(reply))                # type: ignore[arg-type]
    assert [entry["file"] for entry in out["tier2"]] == ["b.py", "a.py"]
    assert "DROP_TABLE" not in str(out)


def test_a_chunk_the_judge_dropped_is_MOVED_not_deleted() -> None:
    """Completeness beats ordering. The floors exist so a bundle can only
    gain files; a judge that deletes one would undo that from above — so the
    unpicked go to the tail, flagged, and the caller can still see them."""
    scored = bundle_of("a.py", "b.py", "c.py")
    out = rerank(scored, Judge("[1]"))                # type: ignore[arg-type]
    assert len(out["tier2"]) == 3
    assert out["tier2"][0]["file"] == "b.py"
    assert {e["file"] for e in out["tier2"][1:]} == {"a.py", "c.py"}


@pytest.mark.parametrize("reply", ["not json at all", "BOOM", "[99, 100]", ""])
def test_every_failure_returns_the_deterministic_bundle_UNTOUCHED(reply: str) -> None:
    """No key, a timeout, a malformed reply, ids that do not exist — the judge
    is an optimisation and never a dependency."""
    scored = bundle_of("a.py", "b.py", "c.py")
    before = [entry["file"] for entry in scored["tier2"]]        # type: ignore[union-attr]
    out = rerank(scored, Judge(reply))                # type: ignore[arg-type]
    assert [entry["file"] for entry in out["tier2"]] == before


def test_an_empty_verdict_is_legitimate_and_changes_nothing() -> None:
    """`[]` means "none of these" — a real answer, not a protocol failure. It
    still must not empty the bundle."""
    scored = bundle_of("a.py", "b.py")
    out = rerank(scored, Judge("[]"))                 # type: ignore[arg-type]
    assert len(out["tier2"]) == 2


def test_candidates_are_judged_in_SMALL_BATCHES() -> None:
    """Measured, not chosen: one 29-candidate call missed 3 of 18 targets that
    batches of 8 all kept. Small pools stop the judge ruling files out
    confidently."""
    scored = bundle_of(*[f"f{n}.py" for n in range(RERANK_BATCH * 2 + 3)])
    judge = Judge("[0]")
    rerank(scored, judge)                             # type: ignore[arg-type]
    assert judge.calls == 3, f"{judge.calls} calls for {RERANK_BATCH * 2 + 3} candidates"


def test_one_failed_batch_fails_the_WHOLE_rerank_open() -> None:
    """All-or-nothing across batches: a partial verdict is a ranking derived
    from half the evidence, which is worse than the deterministic one."""
    scored = bundle_of(*[f"f{n}.py" for n in range(RERANK_BATCH + 2)])
    before = [entry["file"] for entry in scored["tier2"]]        # type: ignore[union-attr]
    out = rerank(scored, Judge("[0]", "BOOM"))        # type: ignore[arg-type]
    assert [entry["file"] for entry in out["tier2"]] == before


def test_the_prompt_asks_for_the_EDIT_SURFACE_not_the_answer() -> None:
    """The field case this wording came from: the judge dropped the
    constructor, the decorator and the completion hook as "tangential" because
    they do not ANSWER the question, and the reader paid three manual reads to
    get them back. A chunk a change must TOUCH is relevant."""
    judge = Judge("[0]")
    rerank(bundle_of("a.py", "b.py"), judge)          # type: ignore[arg-type]
    prompt = judge.prompts[0].lower()
    assert "constructor" in prompt and "serialization" in prompt
    assert "test files" in prompt, "it must say what to drop, too"
