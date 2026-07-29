"""What one Ruby file requires, resolved to repo files.

`require_relative` is exact — relative to the requiring file. `require` and
`autoload` go through `$LOAD_PATH`, which this cannot read, so the candidates
are the ones that actually occur: the repo root's `lib/<spec>.rb`, the bare
`<spec>.rb`, the requiring file's OWN directory (test suites add it so
`require 'test_helper'` works), and finally any sub-gem's `*/lib/<spec>.rb` —
sinatra ships rack-protection and contrib inside one repository.

Nothing matches means a gem or the stdlib, and that is NO edge: absence of
proof is absence, and a guessed edge hands a reader an unrelated file as
evidence.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from ._paths import normalise

__all__ = ["ruby_files", "ruby_edges", "RubyFiles"]

RubyFiles = frozenset[str]

_REQUIRE = re.compile(
    r"""^\s*(require_relative|require)\s*\(?\s*['"]([^'"]+)['"]""", re.M)
# `autoload :Const, 'path'` loads through the SAME load path as require —
# rack-protection wires every strategy that way, so it IS the import graph.
_AUTOLOAD = re.compile(r"""^\s*autoload\s*\(?\s*:\w+\s*,\s*['"]([^'"]+)['"]""", re.M)
# `autoload :Relation` with NO path — Zeitwerk derives the file from the
# constant, and it is how modern Rails wires an entire namespace. Without it
# the file every ActiveRecord query goes through reports no dependants.
_AUTOLOAD_BARE = re.compile(r"^\s*autoload\s+:([A-Z]\w*)\s*$", re.M)
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def ruby_files(sources: dict[str, str]) -> RubyFiles:
    """Every path in the repo — resolution needs the whole set, once."""
    return frozenset(sources)


def ruby_edges(relpath: str, source: str,
               files: RubyFiles) -> list[tuple[str, str]]:
    """`[(destination, "import")]` for every require this repo can answer."""
    base = PurePosixPath(relpath).parent
    specs = [(match.group(1) == "require_relative", match.group(2))
             for match in _REQUIRE.finditer(source)]
    specs += [(False, match.group(1)) for match in _AUTOLOAD.finditer(source)]
    # Zeitwerk: the constant names a file inside the declaring file's OWN
    # namespace directory (`active_record.rb` -> `active_record/relation.rb`).
    stem = relpath[:-3] if relpath.endswith(".rb") else relpath
    specs += [(True, f"{PurePosixPath(stem).name}/{_underscore(match.group(1))}")
              for match in _AUTOLOAD_BARE.finditer(source)]
    found: set[tuple[str, str]] = set()
    for relative, spec in specs:
        target = _resolve(relpath, base, spec, relative, files)
        if target is not None:
            found.add((target, "import"))
    return sorted(found)


def _underscore(constant: str) -> str:
    """`AssociationRelation` -> `association_relation`, Rails' own inflection.

    Acronyms are handled by the second alternative of `_CAMEL`, so `HTTPError`
    becomes `http_error` rather than `h_t_t_p_error`."""
    return _CAMEL.sub("_", constant).lower()


def _resolve(relpath: str, base: PurePosixPath, spec: str,
             relative: bool, files: RubyFiles) -> str | None:
    if not spec.endswith(".rb"):
        spec += ".rb"
    if relative:
        candidate = normalise(base / spec)
        return candidate if candidate in files and candidate != relpath else None
    hit = next((c for c in (f"lib/{spec}", spec, normalise(base / spec))
                if c in files), None)
    if hit is None:                       # a sub-gem's own lib/, in a monorepo
        hit = next(iter(sorted(f for f in files if f.endswith(f"/lib/{spec}"))), None)
    return hit if hit and hit != relpath else None
