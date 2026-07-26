"""Turning `[[path:from-to]]` into verbatim source.

The same stance the walkthrough splicer takes, at file granularity: the model
NAMES a range and the engine produces the code. It matters more in task mode,
not less — a reader is about to paste this into their editor, and a model that
retypes code is a model that can silently change an operator.

Lines come from the index, which is also what makes a bad citation VISIBLE: a
range that does not exist cannot be quietly rendered as plausible code.
"""

from __future__ import annotations

import re

from ...storage import Store
from ._elide import MAX_QUOTE_LINES, elide
from ._litter import drop_unresolved

__all__ = ["quote_citations", "lines_of", "CITATION", "MAX_QUOTE_LINES"]

CITATION = re.compile(r"\[\[([^\]:]*[./][^\]:]*):(\d+)-(\d+)\]\]")
"""A citation by PATH and line range.

The `[./]` is load-bearing: the walkthrough also cites retrieved chunks by
INDEX, as `[[3:705-731]]`, and `[^\\]:]+` matches `3` just as happily as a path.
Two citation systems share one bracket syntax, and what tells them apart is that
a path always carries a dot or a slash while an index never does."""

_LANG = {"rb": "ruby", "py": "python", "ts": "typescript", "tsx": "tsx",
         "js": "javascript", "go": "go", "rs": "rust", "java": "java",
         "c": "c", "h": "c", "cpp": "cpp", "cs": "csharp", "php": "php",
         "md": "markdown"}


def quote_citations(text: str, store: Store) -> str:
    """Replace every citation with a fenced block of the real lines.

    A range quoted a SECOND time becomes a back-reference, not a second copy.
    Measured: the same body arrived twice — once as the anchor, once under
    "Pattern to follow" — for about 60 duplicated lines of one render, and the
    reader named it as budget the elided closing lines should have had.
    """
    shown: set[tuple[str, int, int]] = set()

    def replace(match: re.Match[str]) -> str:
        path, lo, hi = match.group(1).strip(), int(match.group(2)), int(match.group(3))
        if (path, lo, hi) in shown:
            return f"**`{path}` L{lo}-{hi}** — quoted above"
        shown.add((path, lo, hi))
        return _block(store, path, lo, hi)

    return drop_unresolved(CITATION.sub(replace, text))


def _block(store: Store, path: str, lo: int, hi: int) -> str:
    lines = lines_of(store, path)
    if not lines:
        return f"_(no file `{path}` in the index)_"
    lo, hi = max(1, lo), min(len(lines), max(lo, hi))
    lo = _with_decorators(lines, lo)
    body, note = elide(lines[lo - 1:hi], lo)
    lang = _LANG.get(path.rsplit(".", 1)[-1].lower(), "")
    return (f"**`{path}` L{lo}-{hi}**{note}\n```{lang}\n"
            + "\n".join(body) + "\n```")


def _with_decorators(lines: list[str], lo: int) -> int:
    """Widen a citation upward over the decorators attached to its first line.

    MEASURED: a "complete sibling" cited from `async def test_…` left
    `@needs_pydantic_v2` on the line above, and the agent went and opened the
    file to find out what decorated every test in it. A decorated declaration
    BEGINS at its first decorator — citing from the `def` shows a function the
    file does not contain.
    """
    while lo > 1 and lines[lo - 2].lstrip().startswith("@"):
        lo -= 1
    return lo


def lines_of(store: Store, path: str) -> list[str]:
    """The file reassembled from its chunks — an exact line partition, so the
    concatenation is the file."""
    metas = store.chunks.read_file(path)
    lines: list[str] = []
    for meta in sorted(metas, key=lambda m: m.start_line):
        lines.extend((meta.text or "").split("\n"))
    return lines
