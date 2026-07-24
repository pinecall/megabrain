"""Content -> chunks, behind one partition-guaranteed contract.

A language supplies a `ParseFn` (source in, `Parsed` out); `Chunker` does the
rest and guarantees that every line of every file belongs to exactly one chunk.
"""

from __future__ import annotations

from ._breadcrumb import breadcrumb, embed_text
from .cast import Chunker
from .model import DEFAULT_BUDGET, Chunk, FileResult, Symbol, nws, validate_partition
from .units import Parsed, ParseFn, Unit

__all__ = ["Chunk", "Symbol", "FileResult", "validate_partition", "nws",
           "DEFAULT_BUDGET", "Chunker", "Unit", "Parsed", "ParseFn",
           "breadcrumb", "embed_text"]
