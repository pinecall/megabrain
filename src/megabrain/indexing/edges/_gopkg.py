"""The whole-repo Go prepass: which package each file is in, and who declares what.

Go enforces top-level name uniqueness INSIDE a package, so `(dir, package) ->
{name: file}` is an exact map — no type inference needed, which is what makes
the extractor deterministic.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

__all__ = ["GoPackages", "go_packages", "PACKAGE", "STRIP"]

PACKAGE = re.compile(r"^package\s+(\w+)", re.M)

# Top-level declarations only — methods are deliberately absent: a method is
# reachable only through a receiver, so a bare-name or `pkg.Name` match can
# never mean a method, and indexing them would let `binding.Default` hit a
# type's own `Default`.
_TOP_DECL = re.compile(
    r"^(?:func\s+([A-Za-z_]\w*)\s*[([]"
    r"|type\s+([A-Za-z_]\w*)"
    r"|var\s+([A-Za-z_]\w*)"
    r"|const\s+([A-Za-z_]\w*))", re.M)
_DECL_BLOCK = re.compile(r"^(?:var|const|type)\s*\(\n(.*?)^\)", re.M | re.S)
_BLOCK_NAME = re.compile(r"^\t+([A-Za-z_]\w*)|^ +([A-Za-z_]\w*)", re.M)

# Comments and string/char/backtick literals, so the usage scan never matches
# a name mentioned in prose or inside a format string.
STRIP = re.compile(
    r'//[^\n]*|/\*.*?\*/|"(?:[^"\\\n]|\\.)*"|`[^`]*`|\'(?:[^\'\\\n]|\\.)*\'', re.S)

Key = tuple[str, str]                     # (directory, package name)


@dataclass(frozen=True, slots=True)
class GoPackages:
    declares: dict[Key, dict[str, str]]   # where each top-level name lives
    package_of: dict[str, Key]
    files: dict[Key, list[str]]
    packages_in: dict[str, set[str]]      # dir -> its package names

    def primary(self, directory: str) -> str | None:
        """The directory's real package, skipping the external `_test` one."""
        names = sorted(p for p in self.packages_in.get(directory, ())
                       if not p.endswith("_test"))
        return names[0] if names else None


def go_packages(sources: dict[str, str]) -> GoPackages:
    declares: dict[Key, dict[str, str]] = defaultdict(dict)
    package_of: dict[str, Key] = {}
    files: dict[Key, list[str]] = defaultdict(list)
    for relpath in sorted(sources):
        if not relpath.endswith(".go"):
            continue
        match = PACKAGE.search(sources[relpath])
        if not match:
            continue
        directory = str(PurePosixPath(relpath).parent)
        key = ("" if directory == "." else directory, match.group(1))
        package_of[relpath] = key
        files[key].append(relpath)
        for name in _declared(sources[relpath]):
            declares[key].setdefault(name, relpath)
    packages_in: dict[str, set[str]] = defaultdict(set)
    for directory, package in package_of.values():
        packages_in[directory].add(package)
    return GoPackages(dict(declares), package_of, dict(files), dict(packages_in))


def _declared(source: str) -> set[str]:
    names = {group for match in _TOP_DECL.finditer(source)
             for group in match.groups() if group}
    for block in _DECL_BLOCK.finditer(source):
        names |= {group for match in _BLOCK_NAME.finditer(block.group(1))
                  for group in match.groups() if group}
    return names
