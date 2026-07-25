"""Building the task prompt — including the footgun that broke every call.

The prompt is mostly code-shaped text and it grows with every lesson learned.
The moment a rule about closing delimiters wrote a literal `}` into it,
`.format()` raised "Single '}' encountered in format string" and EVERY task
call died — a prompt is data, and interpolating it with a mini-language that
reserves braces makes the data able to break the program.
"""

from __future__ import annotations

from megabrain.ask._taskprompt import build_task_prompt
from megabrain.ask._taskwords import PROMPT


def bundle(*files: str) -> dict:
    return {"tier1": [], "tier2": [{"file": f, "symbols": []} for f in files]}


def test_the_task_and_the_map_both_land() -> None:
    out = build_task_prompt("add a redirect_back helper", bundle("lib/app.rb"))
    assert "add a redirect_back helper" in out and "lib/app.rb" in out
    assert "{task}" not in out and "{map}" not in out


def test_a_BRACE_in_the_prompt_does_not_break_it() -> None:
    """The regression. Braces belong in a prompt that talks about code."""
    assert "}" in PROMPT, "the delimiter rule lost its literal brace"
    build_task_prompt("anything", bundle("a.py"))          # must not raise


def test_a_BRACE_in_the_TASK_does_not_break_it() -> None:
    """The same trap from the other side: the caller's own words are data too,
    and a task about JSON or a closure is full of braces."""
    out = build_task_prompt("make it emit {ok: true} on success", bundle("a.py"))
    assert "{ok: true}" in out


def test_an_empty_bundle_still_produces_a_usable_prompt() -> None:
    """Retrieval finding nothing is not a reason to send a prompt with a hole
    in it — the model should be told the map is empty, not shown a blank."""
    out = build_task_prompt("add a thing", bundle())
    assert "nothing found" in out
