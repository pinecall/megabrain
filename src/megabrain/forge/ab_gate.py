"""The empirical judge: does the candidate actually improve retrieval?

The coverage forge is gated by one oracle — `validate_partition` — and for an
UNCOVERED extension that suffices: any legal chunker beats not indexing the
file. SPECIALIZATION rewrites how an already-covered file is chunked, and a
legal chunker can still be *worse* than the built-in. So it needs this second
gate, measured with no human labels against the real index.

The teeth were earned empirically: a generated candidate once scored pooled
IoU 0.55 with median 1-LINE chunks — perfect geometry, useless embeddings.
Rank-aware IoU plus the granularity floor make that family of metric-gaming
un-installable.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..indexing.strategies import Strategy
from .changed import changed_files
from .granularity import granularity_violation
from .measure import index_copy, measure
from .probes import Probe, probe_spans

__all__ = ["ab_gate", "IOU_MARGIN"]

IOU_MARGIN = 0.01          # min absolute pooled-IoU lift for a win


def ab_gate(root: Path | str, candidate: Strategy, *,
            targets: list[str] | None = None, margin: float = IOU_MARGIN,
            regress_tol: float = 0.01, baseline: Strategy | None = None,
            embedder: Any = None) -> dict[str, Any]:
    """WIN requires ALL of: pooled top-chunk IoU lifts by >= margin, pooled
    hit@1 does not regress, no changed file regresses more than regress_tol,
    and no changed file is micro-chunked. 2 and 4 exist because span-IoU alone
    is gameable by 1-line chunks."""
    base = Path(root).resolve()
    files = targets if targets is not None else changed_files(base, candidate, baseline)
    if not files:
        return {"win": False, "reason": "candidate changes no files", "files": []}
    if flaw := granularity_violation(base, candidate, files):
        return {"win": False, "reason": f"degenerate granularity: {flaw}",
                "changed_files": files}
    probes = {f: spans for f in files if (spans := probe_spans(base / f))}
    if not probes:
        return {"win": False, "reason": "no probe spans on changed files",
                "files": files}
    return _verdict(base, candidate, baseline, probes, margin, regress_tol, embedder)


def _verdict(base: Path, candidate: Strategy, baseline: Strategy | None,
             probes: dict[str, list[Probe]], margin: float,
             regress_tol: float, embedder: Any) -> dict[str, Any]:
    champion_tmp, champion = index_copy(base, baseline, embedder)
    challenger_tmp, challenger = index_copy(base, candidate, embedder)
    try:
        per_file: dict[str, Any] = {}
        for relpath, spans in probes.items():
            before = measure(champion, relpath, spans, embedder)
            after = measure(challenger, relpath, spans, embedder)
            per_file[relpath] = {"builtin": before, "candidate": after,
                                 "delta_iou": round(after["mean_iou"]
                                                    - before["mean_iou"], 4)}
    finally:
        shutil.rmtree(champion_tmp, ignore_errors=True)
        shutil.rmtree(challenger_tmp, ignore_errors=True)
    total = sum(len(spans) for spans in probes.values())
    pooled = _pooled(per_file, probes, total)
    worst = min(per_file.values(), key=lambda d: d["delta_iou"])
    win = (pooled["candidate_iou"] - pooled["builtin_iou"] >= margin
           and pooled["candidate_hit1"] >= pooled["builtin_hit1"] - 1e-9
           and worst["delta_iou"] >= -regress_tol)
    return {"win": win,
            "target": max(per_file, key=lambda f: per_file[f]["delta_iou"]),
            "changed_files": list(probes),
            "pooled_builtin_iou": pooled["builtin_iou"],
            "pooled_candidate_iou": pooled["candidate_iou"],
            "delta_iou": round(pooled["candidate_iou"] - pooled["builtin_iou"], 4),
            "pooled_builtin_hit1": pooled["builtin_hit1"],
            "pooled_candidate_hit1": pooled["candidate_hit1"],
            "worst_file_delta_iou": worst["delta_iou"], "per_file": per_file}


def _pooled(per_file: dict[str, Any], probes: dict[str, list[Probe]],
            total: int) -> dict[str, float]:
    def avg(side: str, key: str) -> float:
        return round(sum(float(per_file[f][side][key]) * len(spans)
                         for f, spans in probes.items()) / total, 4)

    return {"builtin_iou": avg("builtin", "mean_iou"),
            "candidate_iou": avg("candidate", "mean_iou"),
            "builtin_hit1": avg("builtin", "hit@1"),
            "candidate_hit1": avg("candidate", "hit@1")}
