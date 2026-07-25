"""Source files this build walked past because nothing can chunk them.

The census's other half. Discovery only looks at extensions some chunker claims,
which is right for indexing and useless for explaining an empty result — a
TypeScript repository comes back with "0 files" and no hint that 412 `.ts` files
were right there.

Data and config are deliberately NOT counted. `package.json`, a lockfile and a
`.png` in the list turn the finding into noise; what a reader needs to know is
which SOURCE this build cannot read yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

__all__ = ["unsupported_sources", "SOURCE_EXTENSIONS"]

SOURCE_EXTENSIONS = frozenset({
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".rb", ".go", ".rs", ".php", ".java", ".kt", ".kts", ".swift", ".m", ".mm",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".scala", ".ex", ".exs", ".erl",
    ".hs", ".lua", ".pl", ".r", ".jl", ".dart", ".zig", ".sh", ".bash", ".zsh",
    ".sql", ".md", ".mdx", ".rst",
})
"""What counts as source for the purpose of saying "I cannot read this".

A list, not a rule, and deliberately generous: being on it only means the census
will NAME the extension. Nothing here is indexed by being listed.
"""

_SKIP_DIRS = frozenset({"node_modules", ".git", "dist", "build", "vendor",
                        "__pycache__", ".venv", "venv", ".next", "target"})


def unsupported_sources(root: Path, supported: Sequence[str]) -> dict[str, int]:
    """extension -> count, for source files no chunker claims. Biggest first."""
    known = frozenset(supported)
    counts: dict[str, int] = {}
    for path in root.rglob("*"):
        if _buried(path, root):
            continue
        suffix = path.suffix.lower()
        if suffix in SOURCE_EXTENSIONS and suffix not in known and path.is_file():
            counts[suffix] = counts.get(suffix, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _buried(path: Path, root: Path) -> bool:
    """Inside a dependency or build directory.

    Checked by NAME on every part rather than by depth: `apps/web/node_modules`
    is as uninteresting as the one at the top, and a census that counts 40000
    vendored `.ts` files has answered a question nobody asked.
    """
    return any(part in _SKIP_DIRS for part in path.relative_to(root).parts)
