"""What the WRITING tools carry in.

Split from the reading ones by what they do to the repository, not by size: a
tool that changes a working tree is a different promise from one that answers a
question, and a reader deciding whether a surface can mutate anything should
find that out by which module they are in.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from .edits import EditOp
from .tools import Repo

__all__ = ["ReplaceParams", "IndexParams"]


class ReplaceParams(TypedDict):
    """One transactional batch of exact-string edits."""

    repo_path: Repo
    operations: Annotated[
        list[EditOp],
        "the edits, as a list of {file, find, replace, count?}. `file` is "
        "repo-relative; `find` is the EXACT existing text, copied from what "
        "megabrain showed you, and it must occur exactly `count` times "
        "(default 1) or the whole batch is refused — add surrounding lines to "
        "make it unique. ALL-OR-NOTHING: if any operation fails, nothing is "
        "written and the report names which one and why. Ops on the same file "
        "see each other's result, so a batch can edit a line and then edit "
        "what it just wrote. Editing existing files only — use your own Write "
        "to create one"]


class _IndexRequired(TypedDict):
    repo_path: Repo


class IndexParams(_IndexRequired, total=False):
    """Build or refresh a repository's index."""

    force: Annotated[bool, "default false: only files whose content changed are "
                           "re-embedded, so a warm re-index costs seconds. true "
                           "re-embeds everything — needed after changing the "
                           "embedding model, and wasteful otherwise"]
