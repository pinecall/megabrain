"""A TASK is not a QUESTION, and they want opposite answers.

MEASURED, and it is why `ask` cost two calls instead of one. Given "add a
redirect_back helper that redirects to the Referer header with a fallback", the
narrator explained the mechanism beautifully — and the agent then had to ask a
SECOND question, verbatim from the transcript:

    "donde esta definido el helper redirect y los otros helpers de sinatra"

The first answer said HOW it works. The agent needed to know WHERE to type.

A question wants the flow narrated across subsystems. A task wants the EDIT
SURFACE: the files that must change, opened, with the place the change goes and
the neighbouring test to imitate. Same retrieval, different deliverable — so
the shape of the request has to be read before the answer is built.

Deterministic and model-free, for the same reason `wants_tests` is: this runs
on the query path of every ask, and a non-deterministic verdict would make the
same request answer differently between runs.
"""

from __future__ import annotations

import pytest

from megabrain.search.intent import is_task

TASKS = [
    "add a redirect_back helper that redirects to the Referer header",
    "implement retry with exponential backoff in the client",
    "fix the crash when the session store is empty",
    "make the parser accept a trailing comma",
    "rename Session to Conversation everywhere",
    "remove the deprecated v1 endpoint",
    "wire the new logger into the request pipeline",
    "support a :cache_control option on send_file",
    "refactor the dispatcher to use a strategy",
    "migrate the config loader to yaml",
    "we need a way to cancel an in-flight call",
]

QUESTIONS = [
    "how does halt interrupt the request",
    "where is the retry backoff computed",
    "why does the session expire early",
    "what happens when the parser sees a malformed token",
    "which test covers pass and forward",
    "explain how routing works end to end",
    # The trap: describing code that ADDS things is not a request to add
    # anything, and it is the phrasing most likely to fool a keyword rule.
    "where does the indexer add chunks to the store",
    "how do the filters get registered when the app boots",
]


@pytest.mark.parametrize("query", TASKS)
def test_a_change_request_is_a_TASK(query: str) -> None:
    assert is_task(query) is True


@pytest.mark.parametrize("query", QUESTIONS)
def test_an_explanation_request_is_NOT_a_task(query: str) -> None:
    assert is_task(query) is False


def test_it_is_deterministic_and_model_free() -> None:
    """It runs on the query path of every ask. A model call here would put a
    network round trip in front of the routing decision, and a
    non-deterministic one would make the same request answer differently
    between runs — the property the whole engine is built to keep."""
    assert is_task("add a helper") == is_task("add a helper")


def test_an_INTERROGATIVE_opening_always_wins() -> None:
    """"how do I add a cache header" is a question about the code, even though
    it says "add". The opening word is what the sentence is FOR."""
    assert is_task("how do i add a cache header") is False
    assert is_task("where should i add the new route") is False
