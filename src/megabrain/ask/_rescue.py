"""The narrator's own call site for `repair`: fix, splice, report — or nothing.

Split from `repair.py` because that module is the REPAIR itself (the prompt,
the one-call round trip, the JSON parsing) and this is the glue that decides
WHEN to call it and what to do with the result — a different kind of change.
"""

from __future__ import annotations

from ..providers.chat import ChatProvider
from ..storage.model import ChunkMeta
from .events import Emit
from .repair import broken_references, repair
from .splice import splice

__all__ = ["rescue"]


def rescue(provider: ChatProvider, raw: str, candidates: list[ChunkMeta],
          emit: Emit) -> list[str]:
    """The references the splice could not resolve, fixed — or nothing.

    Checked against the RAW model output rather than the spliced text: by then
    a resolved citation has become a code block, and what is left is exactly
    what failed. One extra call, only when something broke, and only the broken
    fragments go back — a second full narration would replace prose the reader
    is already reading.
    """
    broken = broken_references(raw)
    if not broken:
        return []
    emit({"type": "repairing", "references": broken})
    fixed = splice(repair(raw, candidates, provider), candidates)
    return [f"\n{fixed}"] if fixed.strip() else []
