"""Which repository a path belongs to.

Every transport needs this and none of them should own it: a CLI is typed from
wherever the developer happens to be standing, an editor sends the file it has
open, and an HTTP request carries whatever the caller pasted. One rule, in one
place — and the place is `storage`, because knowing that an index lives at
`.megabrain/db.sqlite` is this package's knowledge. Both `Store` and every
layer above resolve the layout through `INDEX_FILE`, so the path exists in
exactly one line of the codebase.
"""

from __future__ import annotations

from pathlib import Path

from .._errors import IndexNotFound

__all__ = ["resolve_root", "INDEX_FILE"]

INDEX_FILE = Path(".megabrain") / "db.sqlite"


def resolve_root(start: Path | str) -> Path:
    """The nearest ancestor holding an index, `start` included.

    Upward, the way git finds its repository: nobody works from the root of a
    project, so a tool that only answers when invoked there is a tool people
    stop reaching for. A file is treated as its directory, since an editor
    integration naturally sends the path it has open.
    """
    here = Path(start).expanduser().resolve()
    if here.is_file():
        here = here.parent
    for candidate in (here, *here.parents):
        if (candidate / INDEX_FILE).exists():
            return candidate
    raise IndexNotFound.at(here)
