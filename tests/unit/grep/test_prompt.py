"""The grep prompt's load-bearing clauses, pinned.

The wording IS the behaviour, so a clause that silently disappears is a
behaviour change no other test would catch.
"""

from __future__ import annotations

from megabrain.grep._prompt import GREP_PROMPT


def test_the_prompt_demands_the_origin_of_the_state() -> None:
    """MEASURED across three A/B duels on rails#57197: the agent handed this
    map never read `core.rb` — where `set` DERIVES scheduled_at from wait: —
    and its fix duplicated the state triple in two files, three times out of
    three. The agent that traced the state by hand landed there every time and
    factored. The origin file shares no words with any task about the bug, so
    no lexical lane can rank it: only this pass, which sees the bodies, can
    name it — and it has to be TOLD to."""
    assert "ORIGIN" in GREP_PROMPT
    assert "ASSIGNED" in GREP_PROMPT, "the origin is the assignment, not a reader"
    assert "OPEN files until" in GREP_PROMPT, "the map may not contain it"
    assert "duplicates logic" in GREP_PROMPT


def test_the_prompt_still_forbids_code_and_line_numbers() -> None:
    assert "Do NOT quote code" in GREP_PROMPT
    assert "Do NOT write line numbers" in GREP_PROMPT
    assert "Include the TEST" in GREP_PROMPT
