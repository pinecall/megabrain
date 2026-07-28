"""`megabrain forge [path]` — write a chunker for what the index cannot read.

An explicit user action, and loud on failure: the model writes code exactly
once, here, gated by the partition oracle — a bad chunker cannot be installed,
and index time only ever runs vetted, trusted code.
"""

from __future__ import annotations

import argparse
import json

from ....forge import forge, render_report

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser(
        "forge", help="generate + validate + install a chunking strategy for "
                      "uncovered file types")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--ext", default=None,
                        help="only this extension (e.g. sql or .sql)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and show the code, install nothing")
    parser.add_argument("--attempts", type=int, default=3, metavar="N",
                        help="generate-validate-repair rounds per extension")
    parser.add_argument("--model", default=None,
                        help="code-gen model ($MEGABRAIN_FORGE_MODEL, else the "
                             "repo's narrator model)")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    report = forge(args.path, ext=args.ext, dry_run=args.dry_run,
                   attempts=args.attempts, model=args.model)
    return json.dumps(report, indent=2) if args.json else render_report(report)
