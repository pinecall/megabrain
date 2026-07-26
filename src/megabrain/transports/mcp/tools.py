"""The tools an agent can see — five, and each one earns its slot.

Every tool costs the calling agent context and a decision, so the surface is
the shortest one that CLOSES the loop: understand it, map it, change it, and
make a repository answerable at all.

`replace` is the one that looks redundant and is not. The host has an editor —
but that editor requires a prior Read of the same file, so every body megabrain
already rendered gets paid for twice. It is here on arithmetic, not capability.

Reading a span is still the caller's own tool: a surface that offers its own
invites the agent to re-verify what the render already showed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...contracts.tools import AskParams, CodeParams, SearchParams
from ...contracts.tools_write import IndexParams, ReplaceParams
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
         "UNDERSTAND an indexed repository: a how/where/why question gets a "
         "walkthrough of the whole relevant flow with the REAL code spliced in "
         "at each step — verbatim from disk, true line numbers, so the CODE is "
         "never invented; the prose around it is model narration, so check its "
         "claims against the code it quotes, especially on a root-cause "
         "question. Retrieval itself runs no model. Use this INSTEAD OF "
         "opening files one by one, and do not chain one call per "
         "sub-question: one ask covers a flow. If you already know you are "
         "going to CHANGE something, use megabrain_code instead — this "
         "explains how the code works and still leaves you hunting for where "
         "to type.",
         AskParams),
    Tool("megabrain_code",
         "CHANGE an indexed repository: describe the change and get its EDIT "
         "SURFACE — every file you must touch, the exact anchor to touch it "
         "at, and a prose SPEC of the new code (never the code itself: you "
         "write that, because you run the tests). Cited VERBATIM alongside: "
         "the original the change mirrors, the DEFINITION of every helper the "
         "spec names, the tests that pin the behaviour, and the test file's "
         "imports. Everything you need is IN the surface — do not follow up "
         "with megabrain_ask for a helper's body, it is already quoted. Then "
         "write your code and apply it with megabrain_replace, using the "
         "quoted anchor text as `find` — copy it from the render, it is "
         "verbatim from the index. Describe the OUTCOME you want, not the file "
         "you guess it lives in — finding that is the job.",
         CodeParams),
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
    Tool("megabrain_replace",
         "Apply a BATCH of exact-string edits in one call, transactionally. "
         "Use it instead of your own Edit for code megabrain already showed "
         "you: your editor requires a prior Read of the same file, so every "
         "body you were just shown gets paid for twice. Each operation is "
         "{file, find, replace, count?} and `find` is the EXACT existing text "
         "— copy it from what you were shown. ALL-OR-NOTHING: if any operation "
         "fails nothing is written at all, and the report names the operation, "
         "the reason, and the nearest real line when your text did not match. "
         "Ops on the same file see each other's result. Existing files only. "
         "Run the tests afterwards — the edit is not the end of the task.",
         ReplaceParams),
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
