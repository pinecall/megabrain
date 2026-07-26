"""One module per language: a table, and the walk bound to it.

These are the thinnest files in the engine — `c.py` is thirteen lines, `go.py`
eighteen — because a language contributes a `LangSpec` and nothing else. Eleven
of them sitting beside the chunking engine made the engine hard to find: the
top level of `chunkers/` read as thirty-one peers when it is really three
mechanisms plus a list of bindings.

Nothing is re-exported here on purpose. A caller asks for the language it wants
(`from ..chunkers.languages import ruby`), so adding a language never touches a
file that already works — the registry in `indexing/_languages.py` is the only
place that decides which ones ship on.
"""

from __future__ import annotations

__all__: list[str] = []
