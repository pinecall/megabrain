"""Go-to-definition for one file: `"line:name"` -> where it is defined.

The studio's code panes link only what this resolves, and the restraint is the
feature. A link that lands on the wrong file is worse than no link, because it
still looks authoritative — so the uniqueness of a definition is never taken as
evidence. `Path(root).resolve()` resolves to pathlib; that the repo happens to
have exactly one `resolve` proves nothing about this call.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ...storage import Store
from ...storage.rows import SymbolRow
from ..aliases import alias_files
from .locals import constructors
from .source import file_source
from .uses import py_uses

__all__ = ["file_links"]

Target = dict[str, object]


def file_links(store: Store, root: Path | str, relpath: str) -> dict[str, Target]:
    if not relpath.endswith(".py"):
        return {}
    source = file_source(store, root, relpath)
    parsed = py_uses(source)
    if parsed is None:
        return {}
    try:
        traced = constructors(ast.parse(source))
    except SyntaxError:
        return {}
    finder = _Finder(store, relpath, parsed.aliases, traced)
    found: dict[str, Target] = {}
    for name, sites in parsed.sites.items():
        for line, receiver in sites:
            where = finder.locate(name, receiver)
            # A definition does not link to itself: the `def shout` line in the
            # file that owns it is where the reader already is.
            if where is not None and where != {"file": relpath, "line": line}:
                found[f"{line}:{name}"] = where
    return found


class _Finder:
    """Resolution with the per-file caches it needs. One instance per file."""

    def __init__(self, store: Store, relpath: str, aliases: dict[str, tuple[int, str]],
                 traced: dict[str, str]) -> None:
        self.store = store
        self.relpath = relpath
        self.aliases = aliases
        self.traced = traced
        self.paths = store.files.all_paths()
        self.symbols: dict[str, list[SymbolRow]] = {}
        self.own = {str(entry["name"]).rsplit(".", 1)[-1]: entry
                    for entry in self._symbols_of(relpath)}

    def locate(self, name: str, receiver: str | None) -> Target | None:
        if receiver is None:
            return self._plain(name)
        if receiver in self.traced:        # `var = Alias(...)` -> the ctor's file
            return self._via_alias(self.traced[receiver], name)
        return self._via_alias(receiver, name)

    def _plain(self, name: str) -> Target | None:
        """A bare call or the import site itself: the alias if there is one,
        otherwise a definition in this very file."""
        if name in self.aliases:
            reached = alias_files(self.paths, self.relpath, *self.aliases[name])
            if reached:
                return self._def_in(reached, name) or \
                    {"file": sorted(reached)[0], "line": 1}   # a module, not a symbol
        if name in self.own:
            return {"file": self.relpath, "line": self.own[name]["line"]}
        return None

    def _via_alias(self, alias: str, name: str) -> Target | None:
        info = self.aliases.get(alias)
        if info is None:
            return None
        reached = alias_files(self.paths, self.relpath, *info)
        return self._def_in(reached, name) if reached else None

    def _def_in(self, files: set[str], name: str) -> Target | None:
        for relpath in sorted(files):
            for entry in self._symbols_of(relpath):
                if str(entry["name"]).rsplit(".", 1)[-1] == name:
                    return {"file": relpath, "line": entry["line"]}
        return None

    def _symbols_of(self, relpath: str) -> list[SymbolRow]:
        if relpath not in self.symbols:
            self.symbols[relpath] = self.store.symbols.read_for(relpath)
        return self.symbols[relpath]
