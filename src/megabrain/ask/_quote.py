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

from ..storage import Store

__all__ = ["quote_citations", "lines_of", "CITATION", "MAX_QUOTE_LINES"]

MAX_QUOTE_LINES = 40
"""Lines any single citation may print before it is cut, LOUDLY.

Enforced here because asking did not work. Told to cite "one test, or one
method — not the class or describe that contains it", the model cited a
117-line `describe` block holding fifteen tests: 3 518 characters, 55% of the
whole answer, to show what one of them looks like. Forty lines is two or three
complete examples, which is what imitating a style actually needs.

Display only. The APPLY markers are read from the raw text before any quoting,
so a cut here can never shorten the anchor an edit is built from.
"""

CITATION = re.compile(r"\[\[([^\]:]+):(\d+)-(\d+)\]\]")

_LANG = {"rb": "ruby", "py": "python", "ts": "typescript", "tsx": "tsx",
         "js": "javascript", "go": "go", "rs": "rust", "java": "java",
         "c": "c", "h": "c", "cpp": "cpp", "cs": "csharp", "php": "php",
         "md": "markdown"}


def quote_citations(text: str, store: Store) -> str:
    """Replace every citation with a fenced block of the real lines."""
    return CITATION.sub(lambda m: _block(store, m.group(1).strip(),
                                         int(m.group(2)), int(m.group(3))), text)


def _block(store: Store, path: str, lo: int, hi: int) -> str:
    lines = lines_of(store, path)
    if not lines:
        return f"_(no file `{path}` in the index)_"
    lo, hi = max(1, lo), min(len(lines), max(lo, hi))
    lo = _with_decorators(lines, lo)
    shown = min(hi, lo + MAX_QUOTE_LINES - 1)
    body = "\n".join(lines[lo - 1:shown])
    cut = (f"\n… cut at L{shown} of L{lo}-{hi}" if shown < hi else "")
    lang = _LANG.get(path.rsplit(".", 1)[-1].lower(), "")
    return f"**`{path}` L{lo}-{hi}**\n```{lang}\n{body}\n```{cut}"


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
