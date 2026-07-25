"""What a tool call carries in — the inputs, as types.

The other contracts describe what the engine RETURNS; these describe what a
calling agent sends. They live here for the same reason: the MCP `inputSchema`
is generated from them (`transports/mcp/schema.py`), so a parameter is declared
once and cannot exist on the wire without existing in the dispatch, or the
reverse — which is how a tool ends up advertising a flag nobody reads.

The descriptions are part of the contract, not decoration. They are the only
thing the calling agent reads before choosing arguments, and every line in them
is a lesson from a real session.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from .._types import Content

__all__ = ["AskParams", "CodeParams", "SearchParams"]

Repo = Annotated[str, "path to the indexed repository root; a path INSIDE it "
                      "also works — the root is found from .megabrain"]

Scope = Annotated[str, "optional repo-relative folder to answer from; omit for "
                       "the whole repository. Scoping EXCLUDES everything "
                       "outside it from retrieval, so scope to a package ROOT "
                       "(e.g. activejob), never to its src/ or lib/ subfolder "
                       "— that cuts away the package's tests, which are "
                       "usually the spec of the behaviour you are asking about"]


class _Target(TypedDict):
    """Which repository. Every tool needs it; none of them guesses it."""

    repo_path: Repo


class _AskRequired(_Target):
    query: Annotated[str, "a how/where/why question, in natural language"]


class AskParams(_AskRequired, total=False):
    scope_path: Scope
    content: Annotated[Content, "'code' (the default) or 'docs'. A code "
                                "walkthrough diluted with prose explains the "
                                "documentation instead of the mechanism, so "
                                "this is one or the other, never a blend"]


class _SearchRequired(_Target):
    task: Annotated[str, "the feature, question or bug, in natural language. "
                         "On a bug, name the STATE to track rather than the "
                         "symptom: 'where along this path could scheduled_at "
                         "be lost?' returns a trace; 'why does the retry fire "
                         "immediately?' invites a theory"]


class SearchParams(_SearchRequired, total=False):
    scope_path: Scope
    content: Annotated[Content, "omit to let code and docs compete; 'code' so "
                                "a long README cannot outrank the code it "
                                "describes; 'docs' for prose only"]
    bodies: Annotated[bool, "default FALSE: the answer is a MAP — the files "
                            "that answer the task, each with its best span and "
                            "its symbols, no code. Measured at ~2 700 tokens "
                            "against ~8 100 with bodies, and the span tells you "
                            "where to look. true inlines the code when you want "
                            "to read it here instead of opening the file"]
    rerank: Annotated[bool, "default false: the deterministic answer is "
                            "complete on its own. true asks a model to reorder "
                            "the related files by the task's edit surface — a "
                            "chat call, a second or two, and it never drops a "
                            "file"]
    expand: Annotated[bool, "default false. true asks a model to name the "
                            "identifiers your wording MISSED — the method or "
                            "class the code itself uses — and searches again "
                            "for them, up to three rounds, stopping when a "
                            "round adds nothing. Buys RECALL where rerank buys "
                            "ORDER: reach for it when the answer plainly is not "
                            "in the list, not by default"]


class _CodeRequired(_Target):
    task: Annotated[str, "the CHANGE you are about to make, in the imperative: "
                         "'add a redirect_back helper that falls back to a "
                         "given path'. Describe the outcome, not the file — "
                         "finding the file is what this does"]


class CodeParams(_CodeRequired, total=False):
    scope_path: Scope
