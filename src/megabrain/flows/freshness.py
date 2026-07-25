"""Is the code a flow described still the code on disk?

Checked against DISK, not against the index's shas, and that is deliberate: the
index legitimately lags disk between runs, and a flow whose sources are
untouched stays valid through that window. Expiring it because something ELSE
was re-indexed would throw away good answers for no reason.

The index-time prune is the second line of defence, not this one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["files_current", "sha_of"]


def files_current(root: Path | str, files: dict[str, str]) -> bool:
    """True when every cited file is still byte-identical on disk."""
    base = Path(root)
    return all(sha_of(base / relpath) == sha for relpath, sha in files.items())


def sha_of(path: Path) -> str:
    """The same content hash indexing uses, so the two agree by construction.

    A missing file hashes to "", which matches no stored sha — so a vanished
    source invalidates its flow without needing a separate branch.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
