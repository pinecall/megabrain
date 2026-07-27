"""What to ask a repository you have never read.

The hardest part of using this engine is the blank input. A repo can answer that
for its readers by committing `queries` to `megabrain.json`; when it has not —
and measured across a whole machine, none had — the index itself knows enough to
propose something, with no model and no network.

Two derived shapes, because they are the two questions a newcomer to any
codebase actually has: what is this load-bearing file for, and where does this
name I keep seeing live. Both are facts already in the graph and the symbol
table, which is what makes them cheap and what keeps them honest.

The SOURCE travels with them. "The repository asked for this" and "we derived
this from the import graph" must never look alike on screen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from ..graph.build import load_graph
from ..project import load_project
from ..search.paths import is_test
from ..storage import Store
from ..storage.locate import resolve_root

__all__ = ["Starters", "starters_for", "DERIVED_FILES", "DERIVED_SYMBOLS"]

DERIVED_FILES = 3
DERIVED_SYMBOLS = 3


class Starters(TypedDict):
    source: Literal["file", "derived", "none"]
    queries: list[str]


def starters_for(start: Path | str) -> Starters:
    """The repository's own questions, or ones derived from its index."""
    root = resolve_root(start)
    declared = load_project(root).queries
    if declared:
        return Starters(source="file", queries=list(declared))
    derived = _derived(root)
    return Starters(source="derived" if derived else "none", queries=derived)


def _derived(root: Path) -> list[str]:
    graph = load_graph(str(root))
    core = [relpath for relpath in
            sorted(graph.files, key=lambda f: (-graph.in_degree(f), f))
            if not is_test(relpath) and graph.in_degree(relpath) > 0
            and not relpath.endswith("__init__.py")][:DERIVED_FILES]
    return [*(f"what is {Path(relpath).name} for, and who depends on it?"
              for relpath in core),
            *(f"where is {name} implemented?" for name in _names(root, core))]


def _names(root: Path, core: list[str]) -> list[str]:
    """The most prominent declared names in the most depended-on files.

    Taken from the symbol table rather than from the text: a name that is
    DECLARED is a name worth asking about, while one that merely appears is
    usually a call to somebody else's code.
    """
    found: list[str] = []
    with Store(root) as store:
        for relpath in core:
            for entry in store.symbols.read_for(relpath):
                name = str(entry["name"]).rsplit(".", 1)[-1]
                if len(name) > 3 and not name.startswith("_") and name not in found:
                    found.append(name)
                    break
    return found[:DERIVED_SYMBOLS]
