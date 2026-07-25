"""The expander: widening a pool the judge could only ever reorder.

The failure it exists for, in one sentence from the version this ports:
"the judge can only reorder what cosine FOUND; when the cause never enters the
pool no reordering rescues it."

Measured on sinatra, that is exactly what happened — the four canonical `halt`
tests never entered the bundle, so the judge had nothing to promote and two
agents fell back to grep.

Three properties make it safe to spend a model call on:

  * the model NAMES SEARCH TERMS, never files and never spans. A bad term costs
    one wasted lane; it can never put a wrong span in front of a reader.
  * the search it triggers is the ordinary deterministic one, so everything the
    expansion admits went through the same scoring as everything else.
  * it only ever ADDS. Like the recall floors, completeness can rise and never
    fall — which is what makes an extra lane strictly better than no lane.

And it LOOPS: one round names the vocabulary the query lacked, the next names
what the first round's findings revealed. It stops when a round adds nothing —
"until dry" rather than a fixed count, because the right number of rounds is a
property of the repository, not of the caller.
"""

from __future__ import annotations

from typing import Any

import pytest

from megabrain.enrich.expand import MAX_ROUNDS, expand


class Namer:
    """Replies with whatever terms the test scripts, one round per reply."""

    model = "namer"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls = 0
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        self.prompts.append(prompt)
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        if reply == "BOOM":
            raise RuntimeError("the namer fell over")
        return reply


def file_entry(name: str, score: float = 0.5) -> dict[str, Any]:
    return {"file": name, "score": score, "via_graph": False, "matched": [],
            "doc": None, "best_chunk": None, "symbols": []}


def bundle_of(*files: str) -> dict[str, Any]:
    return {"query": "where are the tests for halt", "repo": "r", "ms": 5,
            "tier1": [], "flows": [], "anchors": [], "judge": None,
            "evidence": "weak", "top_cosine": 0.3,
            "tier2": [file_entry(name) for name in files]}


def searcher(**by_term: list[str]):
    """A stand-in for the symbol resolver: identifier -> the files defining it.

    The real one is `retrieval/bundle/widen.py`; what this module owns is the
    conversation, so the resolution is injected and stubbed here.
    """
    seen: list[str] = []

    def run(terms: list[str], held: set[str]) -> list[dict[str, Any]]:
        seen.extend(terms)
        found = [f for term in terms for f in by_term.get(term, [])]
        return [file_entry(f) for f in dict.fromkeys(found) if f not in held]

    run.seen = seen        # type: ignore[attr-defined]
    return run


def test_a_file_the_first_search_MISSED_is_admitted() -> None:
    """The whole point. `routing_test.rb` was invisible to the query's own
    vocabulary and one named term reaches it."""
    bundle = bundle_of("base.rb")
    out = expand(bundle, Namer('["routing_test"]'),  # type: ignore[arg-type]
                 searcher(routing_test=["test/routing_test.rb"]))
    assert [f["file"] for f in out["tier2"]] == ["base.rb", "test/routing_test.rb"]


def test_it_only_ADDS_and_never_reorders_what_was_there() -> None:
    """Same contract as the recall floors: an extra lane must not be able to
    make a bundle worse, or nobody can afford to leave it on."""
    bundle = bundle_of("a.py", "b.py", "c.py")
    before = [f["file"] for f in bundle["tier2"]]
    out = expand(bundle, Namer('["x"]'),  # type: ignore[arg-type]
                 searcher(x=["d.py"]))
    assert [f["file"] for f in out["tier2"]][:3] == before


def test_a_file_already_present_is_not_duplicated() -> None:
    out = expand(bundle_of("a.py"), Namer('["x"]'),  # type: ignore[arg-type]
                 searcher(x=["a.py", "b.py"]))
    assert [f["file"] for f in out["tier2"]] == ["a.py", "b.py"]


def test_it_LOOPS_until_a_round_adds_nothing() -> None:
    """Round two names what round one's findings revealed. Stopping at one call
    is a guess about how deep the answer is; stopping when nothing new arrives
    is a measurement of it."""
    namer = Namer('["first"]', '["second"]', '["third"]')
    run = searcher(first=["one.py"], second=["two.py"], third=[])
    out = expand(bundle_of("start.py"), namer, run)  # type: ignore[arg-type]
    assert [f["file"] for f in out["tier2"]] == ["start.py", "one.py", "two.py"]
    assert namer.calls == 3, "it stopped before the round that added nothing"


def test_the_loop_is_BOUNDED() -> None:
    """A namer that keeps finding new things must not spin: every round costs a
    model call and the caller is waiting."""
    namer = Namer('["more1"]', '["more2"]', '["more3"]', '["more4"]', '["more5"]')
    counter = {"n": 0}

    def endless(terms: list[str], _held: set[str]) -> list[dict[str, Any]]:
        counter["n"] += len(terms)
        return [file_entry(f"file{counter['n']}.py")]

    expand(bundle_of("start.py"), namer, endless)  # type: ignore[arg-type]
    assert namer.calls <= MAX_ROUNDS, f"{namer.calls} rounds is a spin"


def test_a_term_that_only_ECHOES_the_query_is_dropped() -> None:
    """It would re-search the same pool for the same words — a wasted round
    trip that also reads as progress. Field case from the port: the model
    echoed the query's own identifiers back despite being told not to."""
    namer = Namer('["halt", "tests"]')
    run = searcher(halt=["x.py"])
    expand(bundle_of("a.py"), namer, run)  # type: ignore[arg-type]
    assert not run.seen, "an echo of the query was resolved"  # type: ignore[attr-defined]


@pytest.mark.parametrize("reply", ["not json", "BOOM", "", "[]"])
def test_every_failure_returns_the_bundle_UNTOUCHED(reply: str) -> None:
    """No provider, a timeout, a malformed reply, an empty verdict — the
    expander is an optimisation and never a dependency."""
    bundle = bundle_of("a.py", "b.py")
    before = [f["file"] for f in bundle["tier2"]]
    out = expand(bundle, Namer(reply), searcher(x=["c.py"]))  # type: ignore[arg-type]
    assert [f["file"] for f in out["tier2"]] == before


def test_the_prompt_shows_what_was_already_FOUND() -> None:
    """A namer that cannot see the pool names terms already in it. The
    instruction to avoid repetition is worthless without the list."""
    namer = Namer('["x"]')
    expand(bundle_of("base.rb", "helpers.rb"), namer,  # type: ignore[arg-type]
           searcher(x=[]))
    assert "base.rb" in namer.prompts[0] and "helpers.rb" in namer.prompts[0]
    assert "where are the tests for halt" in namer.prompts[0]


def test_the_namer_sees_CORE_too_not_just_RELATED() -> None:
    """FOUND IN USE on sinatra. The listing was built from RELATED alone, so
    the four files the bundle was most confident about were invisible to the
    one lane whose entire job is judging what is missing — and a term it named
    could point at a file already sitting in CORE.
    """
    namer = Namer('["x"]')
    bundle = {**bundle_of("related.rb"),
              "tier1": [file_entry("base.rb"), file_entry("helpers.rb")]}
    expand(bundle, namer, searcher(x=[]))  # type: ignore[arg-type]
    assert "base.rb" in namer.prompts[0] and "helpers.rb" in namer.prompts[0]


def test_a_file_already_in_CORE_is_not_re_added_to_RELATED() -> None:
    """The same file in both tiers reads as two findings and costs the reader
    a second look at what they already have."""
    bundle = {**bundle_of("related.rb"), "tier1": [file_entry("base.rb")]}
    out = expand(bundle, Namer('["x"]'),  # type: ignore[arg-type]
                 searcher(x=["base.rb", "new.rb"]))
    assert [f["file"] for f in out["tier2"]] == ["related.rb", "new.rb"]


def test_the_terms_travel_on_the_bundle() -> None:
    """The reader is owed the reason a file appeared: it was not in the answer
    to their question, it was in the answer to a term a model proposed."""
    out = expand(bundle_of("a.py"), Namer('["routing_test"]'),  # type: ignore[arg-type]
                 searcher(routing_test=["t.py"]))
    assert out["expanded"] == ["routing_test"]
