"""When the model's citations do not resolve, the answer is REPAIRED.

Both failures below came out of one real answer, and both had the same effect:
the reader was told a file and a line range and shown no code at all.

    "...refusal fallbacks [[1:173-240], [2:241-307]] and tools for local
     file system interaction `src/anthropic/lib/tools/agent_toolset.py` L688-757"

The first is a GRAMMAR gap — two citations inside one bracket pair, which the
model writes unprompted and the parser rejected wholesale. The second is a
model mistake: it named a file in prose instead of citing a chunk.

A grammar gap gets fixed in the grammar. A model mistake gets ONE scoped
repair call that returns only the corrected citations — never the whole answer
again, which would cost a second full narration and produce different prose.
"""

from __future__ import annotations

import pytest

from megabrain.ask.citations import parse_citations
from megabrain.ask.repair import broken_references, repair
from megabrain.providers.chat.base import Answer
from tests.unit.ask.test_splice import CANDIDATES


class Fixer:
    model = "fixer"
    agent_stream = None

    def __init__(self, reply: str) -> None:
        self.reply, self.calls, self.prompts = reply, 0, []

    def available(self) -> bool:
        return True

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        return self.stream_chat({"messages": [{"content": prompt}]}).text

    def stream_chat(self, body: dict[str, object], *, on_delta: object = None) -> Answer:
        self.prompts.append(str(body["messages"][0]["content"]))  # type: ignore[index]
        self.calls += 1
        if self.reply == "BOOM":
            raise RuntimeError("the fixer fell over")
        return Answer(text=self.reply, finish_reason="stop")


# ---- 1. the grammar gap -----------------------------------------------------


def test_TWO_citations_in_one_bracket_pair_parse() -> None:
    """Exactly what leaked. The model means chunk 1 lines 173-240 AND chunk 2
    lines 241-307 — unambiguous, and rejecting it printed both as prose."""
    found = parse_citations("fallbacks [[1:173-240], [2:241-307]] and tools")
    assert [(c.index, c.ranges) for c in found] == [
        (1, ((173, 240),)), (2, ((241, 307),))]


@pytest.mark.parametrize("text", [
    "[[0], [1]]",
    "[[0:1-2], [1]]",
    "[[0:1-2, 4-6], [1:8-9]]",
])
def test_the_grouped_spellings_all_parse(text: str) -> None:
    assert len(parse_citations(text)) == 2


# ---- 2. what the parser cannot fix ------------------------------------------


def test_a_prose_file_reference_is_DETECTED_as_broken() -> None:
    """The model named a file and a line range instead of citing a chunk.
    Nothing can resolve that, and left alone the reader gets a path and no
    code — which reads like an answer."""
    text = ("tools for local file system interaction "
            "`src/anthropic/lib/tools/agent_toolset.py` L688-757")
    assert broken_references(text) == ["`src/anthropic/lib/tools/agent_toolset.py` L688-757"]


def test_a_malformed_citation_is_detected() -> None:
    assert broken_references("see [[not-a-number]] here") == ["[[not-a-number]]"]


def test_a_correct_answer_needs_no_repair() -> None:
    assert broken_references("the handler is [[0]] and it delegates") == []


def test_inline_code_is_not_mistaken_for_a_reference() -> None:
    """`Stream.__next__` in prose is normal writing, not a broken citation."""
    assert broken_references("the `SSEDecoder` class and `handle()`") == []


# ---- 3. the repair round-trip ------------------------------------------------


def test_only_the_BROKEN_fragments_are_sent_back() -> None:
    """Not the whole answer: a second full narration costs another call and
    comes back with different prose, so the reader watches the answer they
    were reading get replaced."""
    text = ("UNMISTAKABLE_SURROUNDING_TEXT [[0]] more `util.py` L10-12 end")
    fixer = Fixer('["[[1]]"]')
    repair(text, CANDIDATES, fixer)
    prompt = fixer.prompts[0]
    assert "`util.py` L10-12" in prompt
    assert "UNMISTAKABLE_SURROUNDING_TEXT" not in prompt, \
        "the surrounding answer was resent — that is a second full narration"


def test_the_repaired_citation_replaces_the_broken_reference() -> None:
    text = "the runner is `util.py` L10-12 here"
    fixed = repair(text, CANDIDATES, Fixer('["[[1]]"]'))
    assert "[[1]]" in fixed
    assert "`util.py` L10-12" not in fixed


def test_a_reference_the_model_cannot_place_is_DROPPED_not_printed() -> None:
    """An empty answer for a fragment means "no chunk covers this". Better a
    missing sentence fragment than a path with no code under it."""
    text = "see `unknown.py` L1-2 for that"
    fixed = repair(text, CANDIDATES, Fixer('[""]'))
    assert "unknown.py" not in fixed


def test_a_failing_repair_leaves_no_litter_either() -> None:
    """Fail-open means the ANSWER survives, not that the broken text does."""
    text = "see `util.py` L10-12 for that"
    fixed = repair(text, CANDIDATES, Fixer("BOOM"))
    assert "`util.py` L10-12" not in fixed
    assert "see" in fixed and "for that" in fixed


def test_nothing_broken_means_NO_call_at_all() -> None:
    """The repair is a rescue, not a step. A correct answer must not pay for
    it."""
    fixer = Fixer('["[[0]]"]')
    repair("the handler is [[0]]", CANDIDATES, fixer)
    assert fixer.calls == 0
