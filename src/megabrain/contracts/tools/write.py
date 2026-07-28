"""The one tool that CHANGES something: building the index.

Kept apart from the read tools because a read-only deployment refuses exactly
this one, and a promise about effects should be visible in the file layout.
"""

from __future__ import annotations

from typing import Annotated

from ._shared import Target

__all__ = ["IndexParams"]


class IndexParams(Target, total=False):
    """Build or refresh a repository's index."""

    force: Annotated[bool, "default false: only files whose content changed are "
                           "re-embedded, so a warm re-index costs seconds. true "
                           "re-embeds everything — needed after changing the "
                           "embedding model, and wasteful otherwise"]
