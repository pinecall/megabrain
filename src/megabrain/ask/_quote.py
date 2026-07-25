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

__all__ = ["quote_citations", "CITATION"]

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
    lines = _lines_of(store, path)
    if not lines:
        return f"_(no file `{path}` in the index)_"
    lo, hi = max(1, lo), min(len(lines), max(lo, hi))
    body = "\n".join(lines[lo - 1:hi])
    lang = _LANG.get(path.rsplit(".", 1)[-1].lower(), "")
    return f"**`{path}` L{lo}-{hi}**\n```{lang}\n{body}\n```"


def _lines_of(store: Store, path: str) -> list[str]:
    """The file reassembled from its chunks — an exact line partition, so the
    concatenation is the file."""
    metas = store.chunks.read_file(path)
    lines: list[str] = []
    for meta in sorted(metas, key=lambda m: m.start_line):
        lines.extend((meta.text or "").split("\n"))
    return lines
