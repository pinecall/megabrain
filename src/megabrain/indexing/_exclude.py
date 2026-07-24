"""Which paths are not this repository's code.

Two shapes of rule, because people write both without thinking about it: a bare
word means "a directory by this name, wherever it appears", and anything with a
slash or a glob character is a pattern against the repo-relative path.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

__all__ = ["Excluder", "load_ignore", "IGNORE_FILE"]

IGNORE_FILE = ".megabrainignore"

# Universal build, vendor and cache directories. Anything project-specific
# belongs in the repo's own ignore file — baking a project's quirks in here
# would silently apply them to every other repository on the machine.
DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    "coverage", ".next", ".nuxt", ".pytest_cache", ".tox", ".mypy_cache",
    ".ruff_cache", "target", "vendor", ".megabrain",
})

# Instructions for whoever is READING the repository, not content of it.
# Indexing them feeds a search its own operating rules back as documentation,
# and they routinely contain prompts that must never masquerade as this
# project's docs.
FILES = frozenset({"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md"})


@dataclass(frozen=True, slots=True)
class Excluder:
    names: frozenset[str]
    globs: tuple[str, ...]

    @classmethod
    def build(cls, patterns: Iterable[str] = ()) -> "Excluder":
        names: set[str] = set(DIRECTORIES | FILES)
        globs: list[str] = []
        for raw in patterns:
            pattern = raw.strip().rstrip("/")
            if not pattern:
                continue
            if "/" in pattern or any(c in pattern for c in "*?["):
                globs.append(pattern)
            else:
                names.add(pattern)
        return cls(frozenset(names), tuple(globs))

    def excludes(self, relpath: str) -> bool:
        """A bare name matches any SEGMENT; a pattern matches the path.

        Directory patterns compare on the boundary, so `src/disp` never
        excludes `src/dispatcher.py` — a prefix match there would quietly drop
        files nobody meant to drop.
        """
        if self.names & set(relpath.split("/")):
            return True
        return any(relpath == g or relpath.startswith(f"{g}/")
                   or fnmatch(relpath, g) or fnmatch(relpath, f"{g}/*")
                   for g in self.globs)


def load_ignore(root: Path) -> list[str]:
    """Patterns from `<root>/.megabrainignore`: one per line, `#` comments."""
    path = root / IGNORE_FILE
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [stripped for line in lines if (stripped := line.split("#", 1)[0].strip())]
