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
    missing argument, an unindexed repo and a path the index lacks are all
    ordinary traffic, each worth a sentence the agent can act on."""
    handler = HANDLERS.get(name)
    if handler is None:
        return failure(f"no tool named {name} — megabrain serves "
                       f"{', '.join(sorted(HANDLERS))}", "unknown_tool")
    try:
        return answer(handler(args))
    except arg.Missing as err:
        return failure(f"{name}: {err}", "bad_request")
    except FileNotFoundError as err:
        # Expected traffic: a path the index does not hold is the same failure
        # HTTP answers as a 404. Left to the protocol's last-resort catch, it
        # reached the agent as "unexpected".
        return failure(f"{name}: {err}", "not_found")
    except MegabrainError as err:
        return from_engine(err)
