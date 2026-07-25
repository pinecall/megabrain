"""The edit surface, turned into operations `megabrain_replace` can apply.

MEASURED: with the surface as prose, an agent spent two `replace` calls and a
`Read` applying a two-file change it had already been handed. The surface said
where to type; turning that into exact-string operations was left as an
exercise, and the agent did it one file at a time.

The `find` is built HERE, from the index — never by the model. That is the
whole reason this is safe: `replace` matches exact text, so a model retyping
the anchor with one space wrong turns a valid edit into a refusal. The model
names a SPAN it has already cited and the lines to add; the engine reads that
span out of the index and makes it the `find`. Exact by construction.

What the model still authors is the NEW code, which is the one thing it must:
nobody else knows what the change is.
"""

from __future__ import annotations

import re

from ..storage import Store
from ._quote import lines_of

__all__ = ["operations_from", "APPLY"]

# [[path:lo-hi]] · APPLY <mode> · a fenced block of the new lines.
APPLY = re.compile(
    r"\[\[([^\]:]+):(\d+)-(\d+)\]\]\s*\n\s*APPLY\s+(insert_after|replace_span)\s*\n"
    r"```[a-zA-Z0-9_+-]*\n(.*?)```",
    re.DOTALL)


def operations_from(surface: str, store: Store) -> list[dict[str, str]]:
    """Every marked edit in `surface`, as {file, find, replace}.

    Silent about what it cannot build: a malformed marker means the caller gets
    prose and applies it by hand, which is where they already were. A wrong
    operation would be worse than none — it edits.
    """
    operations: list[dict[str, str]] = []
    for path, start, end, mode, added in APPLY.findall(surface):
        anchor = _span(store, path.strip(), int(start), int(end))
        if not anchor:
            continue
        after = mode == "insert_after"
        lines = anchor.split("\n")
        new = _reindent(added.strip("\n"), lines[-1] if after else lines[0])
        operations.append({
            "file": path.strip(),
            "find": anchor,
            "replace": f"{anchor}\n{new}" if after else new,
        })
    return operations


def _reindent(new: str, sibling: str) -> str:
    """Shift `new` so its first line sits at `sibling`'s indentation.

    Done in the ENGINE because asking for it did not work: told twice, in
    rules and by example, to match the anchor's indentation, the model
    produced `def redirect_back` two spaces deeper than the `def back` it sat
    beside. Ruby did not care and a linter would have.

    The whole block moves by ONE delta, so the code's own internal structure is
    preserved — this straightens a block, it never reformats one. A shift that
    would go negative is clamped: losing indentation is worse than keeping it.
    """
    lines = new.split("\n")
    first = next((line for line in lines if line.strip()), "")
    delta = _indent(sibling) - _indent(first)
    if delta == 0:
        return new
    if delta > 0:
        return "\n".join(" " * delta + line if line.strip() else line
                         for line in lines)
    cut = min(-delta, *(_indent(line) for line in lines if line.strip()))
    return "\n".join(line[cut:] if line.strip() else line for line in lines)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _span(store: Store, path: str, lo: int, hi: int) -> str:
    """The cited lines, verbatim from the index, or "" if the range is unreal."""
    lines = lines_of(store, path)
    if not lines or lo < 1 or hi < lo or hi > len(lines):
        return ""
    return "\n".join(lines[lo - 1:hi])
