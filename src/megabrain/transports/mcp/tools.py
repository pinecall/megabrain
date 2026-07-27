"""The tools an agent can see — four, and each one earns its slot.

Every tool costs the calling agent context and a routing decision, and the host
already has Read, Grep and an editor. So the surface carries only what megabrain
alone can do: narrate a mechanism from the whole repository (`ask`), say where a
change lands (`grep`), map it (`search`), and make a repository answerable at all
(`index`).

It was briefly five. `megabrain_code` and `megabrain_replace` were measured
across five tasks in three languages and REMOVED: what carried the value was
the narrator opening files until it had the whole flow, and that now belongs to
`ask` itself. The edit machinery around it kept being thrown away by the readers
it was built for. Reading a span is likewise the caller's own tool — a surface
that offers its own invites the agent to re-verify what the render showed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...contracts.tools import AskParams, GrepParams, IndexParams, SearchParams
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
         "The whole flow behind a how/where/why question, or behind the change "
         "you are about to make — narrated end to end with the REAL code "
         "spliced in at each step, verbatim from the index with true line "
         "numbers, so the CODE is never invented. The narrator OPENS whatever "
         "the retrieved chunks left unexplained (the definition a call lands "
         "on, the caller a function assumes, the test that pins the behaviour) "
         "and keeps reading until the answer is complete, so ONE call replaces "
         "a grep/Read chain — measured at 19 tool calls by hand against 6 with "
         "this, on a 1 220-file repository. Cited alongside, deterministically: "
         "the definition of every helper the prose names, and the tests that PIN "
         "what it describes — which is how a change stops breaking a test 1 600 "
         "lines away that nobody looked at. Do NOT chain one call per "
         "sub-question: one ask covers a flow. The prose is model narration, so "
         "check its claims against the code it quotes, especially on a "
         "root-cause question; retrieval itself runs no model.",
         AskParams),
    Tool("megabrain_grep",
         "WHERE TO LOOK for a change you are about to make — the grep "
         "replacement. Returns the files to open, the symbols inside them worth "
         "opening, each one's EXACT line range from the index, and one line on "
         "why it matters. The lanes run NO MODEL — the rows come from the index "
         "in ~50 ms, which is what lets it stand in for a grep at all; `why: "
         "true` adds one model call for a note per row plus the site whose text "
         "never contains the task's own words, and a task naming no identifier "
         "the index knows falls back to that same pass rather than answering "
         "empty. It quotes NO "
         "code on purpose — your editor opens the file anyway, so a render that "
         "pasted the body would bill you for reading it twice; the line range is "
         "what turns an open into a jump. Use it INSTEAD OF grepping a repo you "
         "have an index for: grep gives you lines that match a string, this "
         "gives you the places that matter for the task, including the ones "
         "whose text your search terms never mention. You do not need to know "
         "the FILE — but DO name the identifiers you already know, the flag you "
         "are extending or the sibling you are copying: measured, naming one was "
         "4x faster and found 3 of 4 key sites against 1 of 4 for pure prose. "
         "Pair it with `why: true` for full coverage (4 of 4, ~1 s).",
         GrepParams),
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
    Tool("megabrain_index",
         "Build or refresh a repository's index. Needed once before anything "
         "else can answer, and again only when you want changes on disk "
         "reflected — indexing is incremental by content hash, so a warm "
         "re-index costs seconds and re-embeds nothing that did not change. "
         "If a tool tells you a repository is not indexed, this is the fix.",
         IndexParams),
)


def listing() -> list[dict[str, Any]]:
    """The `tools/list` payload: description and schema, generated together."""
    return [{"name": tool.name, "description": tool.description,
             "inputSchema": json_schema(tool.params)} for tool in TOOLS]
