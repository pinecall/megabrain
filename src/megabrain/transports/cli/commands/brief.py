"""`megabrain brief <query>` — the mental model for a question, no code walls."""

from __future__ import annotations

import argparse
import json

from ....atlas import render_brief
from ....usecases import brief

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser(
        "brief", help="the mental model for a question: prose, relations and "
                      "interfaces — no code bodies (needs `study` once)")
    parser.add_argument("query", help="the question, in plain words")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--limit", type=int, default=10, metavar="N",
                        help="files in the answer (default: 10)")
    parser.add_argument("--rerank", action="store_true",
                        help="one judge call reorders the files by the task's "
                             "edit surface — same lane as `search --rerank`")
    parser.add_argument("--json", action="store_true",
                        help="the Brief contract as JSON, for piping")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    result = brief(args.path, args.query, limit=args.limit,
                   rerank=args.rerank)
    if args.json:
        return json.dumps(result, indent=2)
    return render_brief(result)
