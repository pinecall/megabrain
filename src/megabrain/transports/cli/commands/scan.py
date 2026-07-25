"""`megabrain scan <path>` — what indexing would read, before paying for it."""

from __future__ import annotations

import argparse
import json

from ....contracts import ScanReport
from ....usecases import scan

__all__ = ["register"]

SHOWN_REASONS = 8


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("scan", help="census a path: what would be indexed")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    report = scan(args.path)
    return json.dumps(report, indent=2) if args.json else _render(report)


def _render(report: ScanReport) -> str:
    by_reason: dict[str, int] = {}
    for entry in report["skipped"]:
        by_reason[entry["reason"]] = by_reason.get(entry["reason"], 0) + 1
    out = [f'{report["name"]}: {report["would_index"]} files would be indexed'
           + ("  (already indexed)" if report["indexed"] else ""),
           "  " + " · ".join(f"{ext} {count}"
                             for ext, count in list(report["by_extension"].items())[:8])]
    if by_reason:
        out.append("  skipped: " + " · ".join(f"{reason} {count}"
                                              for reason, count in by_reason.items()))
    # Named, not just counted: "3 unreadable" tells nobody which three.
    for entry in report["skipped"][:SHOWN_REASONS]:
        if entry["reason"] != "excluded":
            out.append(f'    {entry["reason"]:<12} {entry["file"]}')
    if report["ignore"]:
        out.append("  ignoring: " + ", ".join(report["ignore"]))
    return "\n".join(out)
