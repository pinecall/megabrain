"""The verb `scan`: what an index of this path would contain.

No indexing, no embedding, no cost. It answers the question anybody asks before
pointing this engine at a large repository — "what is it going to read, and
what is it going to skip" — and it answers the second half by NAME, because a
file silently missing from an index is invisible: the search just never returns
it.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ScanReport, SkippedFile
from ..indexing import discover
from ..indexing.builtin import default_registry
from ..indexing.discover import Found
from ..indexing.unsupported import unsupported_sources
from ..project import load_project
from ..storage.locate import INDEX_FILE

__all__ = ["scan"]

MAX_LISTED = 400


def scan(path: Path | str) -> ScanReport:
    """The census for `path`. Raises if it is not a directory."""
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")
    project = load_project(root)
    registry = default_registry()
    found = discover(root, registry.extensions, exclude=project.ignore)
    return ScanReport(
        path=str(root), name=root.name,
        indexed=(root / INDEX_FILE).exists(),
        would_index=len(found.files),
        # Capped, and the cap is VISIBLE in the count above rather than a
        # silently shorter list: a census that truncates without saying so is
        # the thing it exists to prevent.
        skipped=[SkippedFile(file=entry.relpath, reason=entry.reason)
                 for entry in found.skipped[:MAX_LISTED]],
        by_extension=_by_extension(found.files),
        ignore=list(project.ignore),
        # Why an empty census is empty, answered where the question is asked.
        supported=sorted(registry.extensions),
        unsupported=unsupported_sources(root, registry.extensions))


def _by_extension(files: tuple[Found, ...]) -> dict[str, int]:
    """Counts per extension, biggest first — the shape of the repository in one
    line, and how somebody spots that 900 of 1000 files are one generated
    type."""
    counts: dict[str, int] = {}
    for found in files:
        suffix = Path(found.relpath).suffix or "(none)"
        counts[suffix] = counts.get(suffix, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
