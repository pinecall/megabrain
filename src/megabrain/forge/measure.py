"""Retrieval-real scoring over throwaway indexed copies.

Per probe, against real embeddings:

  IoU   = overlap(true span, the file's TOP-RANKED chunk) / union — what a
          user actually gets when the file is retrieved. Deliberately NOT
          best-IoU-over-all-chunks: that measures geometry, not retrieval,
          and micro-chunking games it (a 1-line chunk always exists that
          matches any span; it once scored 0.55 pooled IoU while embedding
          as noise).
  hit@k = an overlapping chunk sits within the top-k GLOBALLY — rank across
          the whole repo, all files competing.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from ..indexing.strategies import Strategy
from .probes import Probe

__all__ = ["measure", "index_copy", "TOPK"]

TOPK = (1, 5)


def measure(root: Path, target: str, probes: list[Probe],
            embedder: Any = None) -> dict[str, float | int]:
    from ..search.scoring.pipeline import score_chunks
    from ..search.state import load_state

    state = load_state(root)
    if embedder is not None:
        state = replace(state, embedder=embedder)
    ious: list[float] = []
    hits = dict.fromkeys(TOPK, 0)
    for query, start, end in probes:
        scored = score_chunks(state, query)
        top_iou, overlap_rank = _first_ranks(scored, target, start, end)
        ious.append(top_iou)
        for k in TOPK:
            hits[k] += overlap_rank is not None and overlap_rank < k
    state.close()
    count = max(1, len(probes))
    return {"mean_iou": round(sum(ious) / count, 4),
            **{f"hit@{k}": round(hits[k] / count, 4) for k in TOPK},
            "n": len(probes)}


def _first_ranks(scored: Any, target: str, start: int, end: int,
                 ) -> tuple[float, int | None]:
    """(the target file's best-ranked chunk's IoU, the global rank of the
    first chunk overlapping the true span)."""
    top_iou: float | None = None
    overlap_rank: int | None = None
    order = np.argsort(-scored.fused, kind="stable")  # pyright: ignore[reportUnknownMemberType]
    for position, index in enumerate(order):
        meta = scored.metas[int(index)]
        if meta.file != target:
            continue
        overlap = max(0, min(end, meta.end_line) - max(start, meta.start_line) + 1)
        if top_iou is None:                 # the file's best-ranked chunk
            union = max(end, meta.end_line) - min(start, meta.start_line) + 1
            top_iou = overlap / union if overlap else 0.0
        if overlap and overlap_rank is None:
            overlap_rank = position
        if overlap_rank is not None:
            break
    return top_iou or 0.0, overlap_rank


def index_copy(root: Path, strategy: Strategy | None,
               embedder: Any = None) -> tuple[Path, Path]:
    """A throwaway checkout indexed with `strategy` injected (None = builtin)."""
    from ..indexing.indexer import index_repo

    scratch = Path(tempfile.mkdtemp(prefix="mb-forge-gate-"))
    copy = scratch / root.name
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns(
        ".megabrain", ".git", "node_modules", "__pycache__"))
    index_repo(copy, strategies=[strategy] if strategy else [], embedder=embedder)
    return scratch, copy
