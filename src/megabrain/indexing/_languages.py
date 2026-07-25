"""The optional languages, and how the registry is assembled.

Split from the strategies themselves because this is the part with a policy in
it: which languages ship on by default, and what happens to the ones whose
grammar is not installed.
"""

from __future__ import annotations

import importlib.util
from typing import Callable

from ..chunkers import Parsed, go, php, ruby, rust
from .strategies import Strategy

__all__ = ["GrammarStrategy", "optional_strategies"]


class GrammarStrategy:
    """A tree-sitter language with chunking but no import graph yet.

    Retrieval works from day one regardless: the graph is an annotation lane,
    and a language without one still gets symbols, chunks and the file-skeleton
    signal. An extractor is added later by giving the strategy edges — never by
    touching the indexer.
    """

    def __init__(self, exts: tuple[str, ...],
                 parse: Callable[[str, str], Parsed]) -> None:
        self.exts = exts
        self._parse = parse

    def parse(self, relpath: str, source: str) -> Parsed:
        return self._parse(relpath, source)

    def edge_context(self, sources: dict[str, str]) -> object:
        return None

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None:
        return None


# (extensions, parser, the grammar package it needs)
_OPTIONAL = [((".rb",), ruby.parse, "tree_sitter_ruby"),
             ((".go",), go.parse, "tree_sitter_go"),
             ((".rs",), rust.parse, "tree_sitter_rust"),
             ((".php",), php.parse, "tree_sitter_php")]


def optional_strategies() -> list[Strategy]:
    """The languages whose grammar is actually installed.

    Gated rather than required: the grammars are wheels with native code, and
    making every install carry four of them to index a Python repository is a
    cost paid by everyone for the benefit of a few. `pip install
    megabrain[languages]` turns them on with no code change.
    """
    return [GrammarStrategy(exts, parse) for exts, parse, module in _OPTIONAL
            if importlib.util.find_spec(module) is not None]
