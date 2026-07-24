"""Builders for storage tests: name only what the test is about.

A test that spells out nine fields to assert on one buries its own point.
Everything here has a sane default; a test overrides the field it cares about.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from megabrain.chunkers.model import Chunk, Symbol


def chunk(file: str = "a.py", *, cid: int = 0, start: int = 1, end: int = 10,
          kind: str = "function", name: str | None = "f", text: str = "def f(): ...",
          part: str | None = None) -> Chunk:
    return Chunk(file=file, kind=kind, name=name, part=part, start_line=start,
                 end_line=end, text=text, breadcrumb=f"repo > {file} > {name}",
                 id=cid)


def symbol(file: str = "a.py", *, name: str = "f", kind: str = "function",
           line: int = 1, end_line: int = 5, signature: str = "def f()",
           decorators: tuple[str, ...] = (), doc: str | None = None) -> Symbol:
    return Symbol(file=file, name=name, kind=kind, line=line, end_line=end_line,
                  signature=signature, decorators=decorators, doc=doc)


def vectors(rows: list[list[float]]) -> Any:
    return np.array(rows, dtype=np.float32)
