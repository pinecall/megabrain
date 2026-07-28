"""forge reports rendered for a human — the CLI's whole output."""

from __future__ import annotations

from typing import Any

__all__ = ["render_report", "render_gate"]


def render_report(report: dict[str, Any]) -> str:
    lines = [f"# megabrain forge · {report['root']}"]
    if report.get("error"):
        lines.append(f"error: {report['error']}")
    if not report["candidates"]:
        lines.append("no uncovered text extensions found — the index already "
                     "sees everything it can.")
    for c in report["candidates"]:
        lines.append(f"- uncovered {c['ext']}: {c['files']} files, {c['bytes']} "
                     f"bytes (samples: {', '.join(c['samples'])})")
    for e in report.get("forged", []):
        if e["ok"]:
            where = e.get("installed") or "(dry-run, not installed)"
            lines.append(f"✓ {e['ext']} strategy forged in {e['attempts']} "
                         f"attempt(s) — {e['validation']} → {where}")
        else:
            lines.append(f"✗ {e['ext']} failed after {e['attempts']} attempt(s): "
                         f"{e.get('validation', 'no attempt ran')[:400]}")
    if report.get("index"):
        ix = report["index"]
        lines.append(f"reindexed: {ix['files']} files, +{ix['chunks']} chunks, "
                     f"{ix['partition_violations']} violations")
    if report.get("seconds") is not None:
        lines.append(f"({report['seconds']}s)")
    return "\n".join(lines)


def render_gate(report: dict[str, Any]) -> str:
    lines = [f"# megabrain specialize · {report['root']}"]
    gate, ext = report.get("gate", {}), report.get("ext", "?")
    where = report.get("installed") or ("(dry-run)" if gate.get("win")
                                        else "not installed")
    if "pooled_candidate_iou" not in gate:            # gate short-circuited
        lines.append(f"· {ext} [rejected] — {gate.get('reason', 'no gate')}")
    else:
        verdict = "WIN" if gate.get("win") else "no gain (rejected)"
        lines.append(
            f"{'✓' if gate.get('win') else '·'} {ext} [{verdict} vs "
            f"{report.get('baseline')}] ({len(gate.get('changed_files', []))} "
            f"file(s) changed): pooled IoU {gate['pooled_builtin_iou']}"
            f"→{gate['pooled_candidate_iou']} (Δ{gate['delta_iou']:+}), "
            f"worst-file Δ{gate['worst_file_delta_iou']:+} → {where}")
    if report.get("index"):
        ix = report["index"]
        lines.append(f"reindexed: {ix['files']} files, +{ix['chunks']} chunks")
    if report.get("seconds") is not None:
        lines.append(f"({report['seconds']}s)")
    return "\n".join(lines)
