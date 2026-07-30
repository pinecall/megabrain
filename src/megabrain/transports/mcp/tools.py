"""The tools an agent can see — four, and each one earns its slot.

Every tool costs the calling agent context and a routing decision, and the host
already has Read, Grep and an editor. So the surface carries only what megabrain
alone can do: narrate a mechanism from the whole repository (`ask`), say where a
change lands (`grep`), map it (`search`), and make a repository answerable at all (`index`).

`megabrain_node` was here and was REMOVED after an A/B on two real fixes. It
answered who imports a file — which the graph already served over CLI and HTTP
— and on the tasks that decided it, that was either the wrong question (a Ruby
bug whose dangerous consumer was a mixin no import graph contains) or a
shortcut with a cost: going straight to the site skipped the file where the
duplicated concept lived, and the fix duplicated it.

`megabrain_code` and `megabrain_replace` were measured across five tasks in
three languages and REMOVED: what carried the value was the narrator opening
files until it had the whole flow, and that now belongs to `ask` itself. The
edit machinery around it kept being thrown away by the readers it was built
for. Reading a span is likewise the caller's own tool — a surface that offers
its own invites the agent to re-verify what the render showed. The wording of
each tool lives in `_descriptions.py`: it is the surface, not documentation
about it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...contracts.tools import (
    AskParams,
    GrepParams,
    IndexParams,
    SearchParams,
)
from ._descriptions import ASK, GREP, INDEX, SEARCH
from .schema import json_schema

__all__ = ["Tool", "TOOLS", "listing"]


@dataclass(frozen=True, slots=True)
class Tool:
    """A name, what it is for, and the contract its arguments satisfy."""

    name: str
    description: str
    params: type[Any]


TOOLS: tuple[Tool, ...] = (
    Tool("megabrain_ask", ASK, AskParams),
    Tool("megabrain_grep", GREP, GrepParams),
    Tool("megabrain_search", SEARCH, SearchParams),
    Tool("megabrain_index", INDEX, IndexParams),
)


def listing() -> list[dict[str, Any]]:
    """The `tools/list` payload: description and schema, generated together."""
    return [{"name": tool.name, "description": tool.description,
             "inputSchema": json_schema(tool.params)} for tool in TOOLS]
