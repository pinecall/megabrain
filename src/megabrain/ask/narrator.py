"""One narrated walkthrough: retrieve, ask, splice, stream.

The single-agent path. It is also the fallback for the multi-agent one, so it
has to stand on its own — a fan-out that fails must degrade to this rather than
to an error.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Bundle, ChunkHit, ChunkRef
from ..providers.chat import ChatProvider
from ..retrieval.paths import is_test
from ..storage.model import ChunkMeta
from .events import Emit, emit_nothing
from .prompt import build_prompt
from .stream import Splicer

__all__ = ["narrate", "candidates_of", "MAX_CANDIDATES"]

MAX_CANDIDATES = 40


def candidates_of(bundle: Bundle) -> list[ChunkMeta]:
    """The chunks the model may cite, CORE first.

    Ordered by tier rather than re-scored: retrieval already ranked these, and
    a second ordering here would be a second opinion nobody asked for. Tests
    come last — they quote the implementation's vocabulary, so they crowd the
    candidate list without explaining the mechanism.
    """
    seen: set[int] = set()
    out: list[ChunkMeta] = []
    for entry in bundle["tier1"]:
        for hit in entry["chunks"]:
            if hit["id"] not in seen:
                seen.add(hit["id"])
                out.append(_meta(hit))
    for related in bundle["tier2"]:
        best = related["best_chunk"]
        if best and best["id"] not in seen:
            seen.add(best["id"])
            out.append(_meta(best))
    out.sort(key=lambda chunk: is_test(chunk.file))     # stable: tests last
    return out[:MAX_CANDIDATES]


def narrate(provider: ChatProvider, question: str, bundle: Bundle, *,
            root: Path | None = None, emit: Emit = emit_nothing) -> str:
    """Ask once, splice as the answer arrives, return the whole walkthrough."""
    del root                       # the splice reads the index, not the disk
    started = time.perf_counter()
    candidates = candidates_of(bundle)
    if not candidates:
        return "no code was retrieved for this question — nothing to walk through"
    splicer = Splicer(candidates)
    parts: list[str] = []
    emit({"type": "narrating", "candidates": len(candidates)})

    def on_delta(delta: str) -> None:
        if ready := splicer.feed(delta):
            parts.append(ready)
            emit({"type": "delta", "text": ready})

    provider.stream_chat(_body(provider, question, candidates), on_delta=on_delta)
    if tail := splicer.flush():
        parts.append(tail)
        emit({"type": "delta", "text": tail})
    emit({"type": "narrated", "ms": int((time.perf_counter() - started) * 1000)})
    return "".join(parts)


def _body(provider: ChatProvider, question: str,
          candidates: list[ChunkMeta]) -> dict[str, object]:
    return {"model": getattr(provider, "model", ""),
            "max_tokens": 2400, "temperature": 0,
            "messages": [{"role": "user",
                          "content": build_prompt(question, candidates)}]}


def _meta(hit: ChunkRef | ChunkHit) -> ChunkMeta:
    """A wire chunk back to the record the splice works with.

    Typed against the CONTRACT rather than a dict: the fields are declared once
    in contracts/, so a rename there becomes an error here instead of a
    KeyError at the first ask.
    """
    return ChunkMeta(
        id=hit["id"], file=hit["file"], kind=hit["kind"], name=hit["name"],
        part=hit["part"], start_line=hit["start_line"], end_line=hit["end_line"],
        text=hit["text"], breadcrumb=hit["breadcrumb"])
