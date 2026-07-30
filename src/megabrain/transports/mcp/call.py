"""Routing one tool call, and the one place a failure becomes an answer.

Split from the handler table because it is a different job: that file says what
each tool does, this one says what the agent is told when a call cannot be
served. The reader is a model, so every expected failure gets a sentence and a
machine-matchable code rather than a traceback the host swallows.
"""

from __future__ import annotations

from typing import Any

from ..._errors import MegabrainError
from . import arguments as arg
from .answers import Answer, answer, failure, from_engine
from .dispatch import HANDLERS

__all__ = ["call_tool"]


def call_tool(name: str, args: dict[str, Any]) -> Answer:
    """Never raises for a failure anyone should expect — an unknown tool, a
    missing argument and an unindexed repo are all ordinary traffic, each worth
    a sentence the agent can act on rather than a traceback the host swallows."""
    handler = HANDLERS.get(name)
    if handler is None:
        return failure(f"no tool named {name} — megabrain serves "
                       f"{', '.join(sorted(HANDLERS))}", "unknown_tool")
    try:
        return answer(handler(args))
    except arg.Missing as err:
        return failure(f"{name}: {err}", "bad_request")
    except MegabrainError as err:
        return from_engine(err)
