"""What one Go file depends on — two lanes, mirroring how Go actually links.

**import lane.** Each in-repo import resolves to its package directory; then
`alias.Name` uses in the comment- and string-stripped source pin the edge to
the file DEFINING `Name`. An import with no attributable use still edges to
the package's representative file, so the dependency is never dropped.

**package lane.** Files of one package call each other with NO import at all —
that IS the dominant structure of a Go repository (gin's root is 40 such
files). A bare use of a name a sibling declares becomes a `call` edge, and the
`(?<![.\\w])` guard rejects `other.Name`, so a dotted use cannot leak in.
"""

from __future__ import annotations

import re

from ._goimports import import_edges, sibling_edges
from ._gopkg import STRIP, GoPackages, go_packages

__all__ = ["go_packages", "go_edges", "GoPackages"]

_IMPORT_ONE = re.compile(r'^import\s+(?:(\w+|\.|_)\s+)?"([^"]+)"', re.M)
_IMPORT_BLOCK = re.compile(r"^import\s*\(\n(.*?)^\)", re.M | re.S)
_IMPORT_LINE = re.compile(r'^\s*(?:(\w+|\.|_)\s+)?"([^"]+)"', re.M)


def go_edges(relpath: str, source: str,
             packages: GoPackages) -> list[tuple[str, str]]:
    key = packages.package_of.get(relpath)
    stripped = STRIP.sub(" ", source)
    found: set[tuple[str, str]] = set()
    for alias, path in _imports(source):
        found |= import_edges(relpath, stripped, alias, path, key, packages)
    if key:
        found |= sibling_edges(relpath, stripped, key, packages)
    return sorted(found)


def _imports(source: str) -> list[tuple[str, str]]:
    found = [(m.group(1), m.group(2)) for m in _IMPORT_ONE.finditer(source)]
    for block in _IMPORT_BLOCK.finditer(source):
        found += [(m.group(1), m.group(2))
                  for m in _IMPORT_LINE.finditer(block.group(1))]
    return found
