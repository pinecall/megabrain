"""The READ tools' inputs — ask, grep, search, node.

The descriptions are part of the contract, not decoration: they are the only
thing a calling agent reads before choosing arguments, and every line is a
lesson from a measured session.
"""

from __future__ import annotations

from typing import Annotated

from ..._types import Content
from ._shared import Scope, Target

__all__ = ["AskParams", "GrepParams", "SearchParams"]


class _AskRequired(Target):
    query: Annotated[str, "a how/where/why question, in natural language"]


class AskParams(_AskRequired, total=False):
    scope_path: Scope
    content: Annotated[Content, "'code' (default) or 'docs'. A code walkthrough "
                                "diluted with prose explains the documentation "
                                "instead of the mechanism — one or the other"]


class _SearchRequired(Target):
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


class _GrepRequired(Target):
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

