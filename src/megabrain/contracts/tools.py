"""What a tool call carries in — the inputs, as types.

The MCP `inputSchema` is GENERATED from these (`transports/mcp/schema.py`), so a
parameter is declared once and cannot reach the wire without existing in the
dispatch — which is how a tool ends up advertising a flag nobody reads.

The descriptions are part of the contract, not decoration: they are the only
thing a calling agent reads before choosing arguments, and every line is a
lesson from a measured session.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from .._types import Content

__all__ = ["AskParams", "GrepParams", "SearchParams", "IndexParams"]

Repo = Annotated[str, "path to the indexed repo root; a path INSIDE it works "
                      "too — the root is found from .megabrain"]

Scope = Annotated[str, "optional repo-relative folder to answer from; omit for "
                       "the whole repository. Scoping EXCLUDES everything "
                       "outside it, so scope to a package ROOT (e.g. activejob), "
                       "never to its src/ or lib/ subfolder — that cuts away the "
                       "package's tests, usually the spec of what you asked about"]


class _Target(TypedDict):
    """Which repository. Every tool needs it; none of them guesses it."""

    repo_path: Repo


class _AskRequired(_Target):
    query: Annotated[str, "a how/where/why question, in natural language"]


class AskParams(_AskRequired, total=False):
    scope_path: Scope
    content: Annotated[Content, "'code' (default) or 'docs'. A code walkthrough "
                                "diluted with prose explains the documentation "
                                "instead of the mechanism — one or the other"]


class _SearchRequired(_Target):
    task: Annotated[str, "the feature, question or bug, in natural language. On "
                         "a bug name the STATE to track, not the symptom: 'where "
                         "could scheduled_at be lost?' returns a trace, 'why does "
                         "the retry fire?' invites a theory"]


class SearchParams(_SearchRequired, total=False):
    scope_path: Scope
    content: Annotated[Content, "omit to let code and docs compete; 'code' so a "
                                "long README cannot outrank the code it "
                                "describes; 'docs' for prose only"]
    bodies: Annotated[bool, "default FALSE: the answer is a MAP — the files that "
                            "answer, each with its best span and its symbols, no "
                            "code. ~2 700 tokens against ~8 100 with bodies, and "
                            "the span tells you where to look. true inlines it"]
    rerank: Annotated[bool, "default false: the deterministic answer is complete "
                            "on its own. true asks a model to reorder the related "
                            "files by the task's edit surface — one chat call, and "
                            "it never drops a file"]
    expand: Annotated[bool, "default false. true asks a model to name the "
                            "identifiers your wording MISSED — the method the "
                            "code itself uses — and searches again, up to three "
                            "rounds. Buys RECALL where rerank buys ORDER: for "
                            "when the answer plainly is not in the list"]


class IndexParams(_Target, total=False):
    """Build or refresh a repository's index."""

    force: Annotated[bool, "default false: only files whose content changed are "
                           "re-embedded, so a warm re-index costs seconds. true "
                           "re-embeds everything — needed after changing the "
                           "embedding model, and wasteful otherwise"]


class _GrepRequired(_Target):
    task: Annotated[str, "the CHANGE you are about to make, in the imperative, "
                         "and NAME the identifiers you already know — the flag "
                         "you extend, the sibling you copy: 'Option has "
                         "show_envvar; add show_envvar_value'. MEASURED: naming "
                         "one was 4x faster (0.23s vs 0.99s) and found 3 of 4 "
                         "key sites against 1 of 4 for prose alone. You still do "
                         "not need the FILE — finding that is this tool's job"]


class GrepParams(_GrepRequired, total=False):
    scope_path: Scope
    why: Annotated[bool, "default false; the rows then come from the index in "
                         "~50 ms when your task names a known identifier. true "
                         "adds one model call (~1 s) for a note per row plus the "
                         "site whose text never contains the task's words — "
                         "measured, that pairing is the only 4-of-4 coverage"]
