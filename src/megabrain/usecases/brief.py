"""The verb `brief`: the mental model for a question.

The cheap half of the atlas: no LLM, no network beyond one query embedding,
an answer in milliseconds. `search` returns the code; `brief` returns what a
reader needs BEFORE the code — what each file is, how they connect, and where
the bodies live.
"""

from __future__ import annotations

from pathlib import Path

from ..atlas import brief_repo
from ..contracts import Brief
from ..storage.locate import resolve_root

__all__ = ["brief"]


def brief(start: Path | str, question: str, *, limit: int = 10,
          embedder: object = None) -> Brief:
    """Answer `question` for whichever repository `start` belongs to.

    `embedder` is the same injection seam as in `search`; production leaves it
    alone and gets the configured one.
    """
    return brief_repo(resolve_root(start), question, limit=limit,
                      embedder=embedder)
