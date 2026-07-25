"""A file's text, for analysis rather than for display.

Disk first, because the AST has to see the code as it IS — the graph views
answer questions about the repository in front of you, not about the snapshot
the last index took. When the file has moved out from under the index, the
stored chunks reconstruct it, line-wise: chunks partition a file by line and
carry no trailing newline, so joining their strings glues each chunk's last
line onto the next chunk's first, losing one line per seam and shifting every
line number after it.
"""

from __future__ import annotations

from pathlib import Path

from ..storage import Store

__all__ = ["file_source"]


def file_source(store: Store, root: Path | str, relpath: str) -> str:
    try:
        return (Path(root) / relpath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        lines = [line for chunk in store.chunks.read_file(relpath)
                 for line in chunk.text.splitlines()]
        return "\n".join(lines)
