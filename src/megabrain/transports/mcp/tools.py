"""The tools an agent can see — three, on purpose.

Every tool costs the calling agent context and a decision, and the host it
runs in already has Read, Grep and an editor. So megabrain exposes only what it
alone can do: the walkthrough, the edit surface, and the mental model. Reading
a span and editing a file are the caller's own tools, and a surface that offers
its own invites the agent to re-verify what the render already showed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...contracts.tools import AskParams, SearchParams
from .schema import json_schema

__all__ = ["Tool", "TOOLS", "listing"]


@dataclass(frozen=True, slots=True)
class Tool:
    """A name, what it is for, and the contract its arguments satisfy."""

    name: str
    description: str
    params: type[Any]


TOOLS: tuple[Tool, ...] = (
    Tool("megabrain_ask",
         "THE tool for a how/where/why question about an indexed repository. "
         "Returns a senior-engineer walkthrough of the whole relevant flow "
         "with the REAL code spliced in at each step — verbatim from disk, "
         "true line numbers, so the CODE is never invented; the prose around "
         "it is model narration, so check its claims against the code it "
         "quotes, especially on a root-cause question. Retrieval itself runs "
         "no model: the bundle is decided in milliseconds and one chat call "
         "explains it. Use this INSTEAD OF opening files one by one — one ask "
         "covers a flow, so do not chain one per sub-question; afterwards read "
         "only the files you will edit.",
         AskParams),
    Tool("megabrain_search",
         "ONE call that MAPS a task's whole edit surface: the files that answer "
         "it ranked, each with its best span (true line numbers) and the "
         "symbols it declares, plus the anchors a change has to touch and the "
         "tests that pin the behaviour. No code bodies by default — the map is "
         "~2 700 tokens against ~8 100 with them, and the span already tells "
         "you which lines to open; pass `bodies: true` to read the code inline "
         "instead. Search once per TASK, not once per facet. One boundary worth "
         "knowing: it ranks what EXISTS, so when the bug is a missing call or "
         "flag it shows you the site to inspect but cannot report the absence.",
         SearchParams),
)


def listing() -> list[dict[str, Any]]:
    """The `tools/list` payload: description and schema, generated together."""
    return [{"name": tool.name, "description": tool.description,
             "inputSchema": json_schema(tool.params)} for tool in TOOLS]
