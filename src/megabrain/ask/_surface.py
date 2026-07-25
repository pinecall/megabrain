"""Assembling what a task answer LOOKS like, as opposed to how it is found.

Split from the loop because the two change for different reasons: the loop is
about conversing with a model until it stops asking for files, and this is
about what the reader gets handed at the end.

There is no whole-file mode here, and that was measured rather than assumed:
the surface is ~1 000 tokens and the same two files whole are ~22 500, while
the agent holding the surface wanted neither — its one Read was a 125-line
window to see the style of the test beside its own.
"""

from __future__ import annotations

import json

__all__ = ["apply_block"]


def apply_block(operations: list[dict[str, str]]) -> str:
    """The whole change as ONE `megabrain_replace` batch.

    MEASURED: handed the surface as prose, an agent spent two `replace` calls
    and a `Read` applying a two-file change it had already been given — it
    rebuilt the exact-string operations itself, one file at a time. They are
    built here instead, from the index, so applying the change is one call and
    the `find` strings cannot be mistyped.
    """
    if not operations:
        return ""
    return ("\n\n## Apply — ONE call, all files at once\n"
            "```json\n" + json.dumps({"operations": operations}, indent=2)
            + "\n```\n")
