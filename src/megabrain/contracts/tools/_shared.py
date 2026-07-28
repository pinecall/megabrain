"""What every tool call carries: which repository, and how far to look.

Declared once because they are the same question on every surface — a tool
that spelled `repo_path` its own way would be a tool an agent gets wrong once
and stops trusting.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

__all__ = ["Repo", "Scope", "Target"]

Repo = Annotated[str, "path to the indexed repo root; a path INSIDE it works "
                      "too — the root is found from .megabrain"]

Scope = Annotated[str, "optional repo-relative folder to answer from; omit for "
                       "the whole repository. Scoping EXCLUDES everything "
                       "outside it, so scope to a package ROOT (e.g. activejob), "
                       "never to its src/ or lib/ subfolder — that cuts away the "
                       "package's tests, usually the spec of what you asked about"]


class Target(TypedDict):
    """Which repository. Every tool needs it; none of them guesses it."""

    repo_path: Repo
