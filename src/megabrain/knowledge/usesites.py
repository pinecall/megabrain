"""Does this file REALLY use a name defined in that one, and where.

The receiver check is the whole point. Three verdicts per call site:

  plain call or import site   verified — the name resolves by itself
  `alias.name(...)`           verified only if the alias resolves to the
                              defining file; rejected outright when the alias
                              resolves elsewhere or outside the repository
  `variable.name(...)`        counted but INFERRED — the receiver's type is not
                              known here, so the use is plausible, not proven

Non-Python content falls back to a word-boundary scan with no line numbers, and
is never marked verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..storage import Store
from .aliases import alias_files
from .source import file_source
from .uses import Uses, py_uses

__all__ = ["UseSite", "use_sites"]


@dataclass(frozen=True, slots=True)
class UseSite:
    lines: list[int]
    verified: bool
    """Whether ANY of these sites resolved by itself. Verified carriers rank
    ahead of inferred ones however many times the inferred one appears: a
    `dict.get` called fifteen times is weaker evidence than one resolved
    import."""


def use_sites(store: Store, root: Path | str, uses_file: str, names: set[str],
              defs_file: str) -> dict[str, UseSite]:
    source = file_source(store, root, uses_file)
    parsed = py_uses(source) if uses_file.endswith(".py") else None
    if parsed is None:
        return {name: UseSite(lines=[], verified=False) for name in names
                if re.search(rf"\b{re.escape(name)}\b", source)}
    paths = store.files.all_paths()
    found: dict[str, UseSite] = {}
    for name in names:
        site = _resolve(parsed, paths, uses_file, defs_file, name)
        if site is not None:
            found[name] = site
    return found


def _resolve(parsed: Uses, paths: set[str], uses_file: str, defs_file: str,
             name: str) -> UseSite | None:
    lines: list[int] = []
    verified = False
    for line, receiver in parsed.sites.get(name, ()):
        if receiver is None:
            lines.append(line)
            verified = True
        elif receiver in parsed.aliases:
            reached = alias_files(paths, uses_file, *parsed.aliases[receiver])
            if reached is None or defs_file not in reached:
                continue           # external, or a DIFFERENT module of ours
            lines.append(line)
            verified = True
        else:
            lines.append(line)     # a variable or `self` receiver: inferred
    return UseSite(lines=lines, verified=verified) if lines else None
