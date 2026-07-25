"""`megabrain search <query>` — the code map for a question."""

from __future__ import annotations

import argparse
import json

from ....retrieval.render import render
from ....usecases import search

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("search", help="find all the code related to a question")
    parser.add_argument("query", help="the question, in plain words")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--path-filter", metavar="PREFIX",
                        help="only files under PREFIX")
    parser.add_argument("--docs", dest="content", action="store_const", const="docs",
                        help="prose only — markdown, guides, changelogs")
    parser.add_argument("--code", dest="content", action="store_const", const="code",
                        help="code only, so a long README cannot outrank it")
    # The MAP is the default. Measured against the alternative on a real
    # bundle: the map costs 2 660 tokens where CORE-with-bodies costs 8 135,
    # and it carries what a reader needs to decide — file, best span, symbols.
    # The code is one `--full` away, or one `get` away for a single file.
    parser.add_argument("--full", action="store_true",
                        help="include the code bodies (default: the map only — "
                             "files, spans and symbols)")
    parser.add_argument("--rerank", action="store_true",
                        help="let a model reorder RELATED by the task's edit "
                             "surface (costs a call; never drops a file)")
    parser.add_argument("--expand", action="store_true",
                        help="let a model name the identifiers the question "
                             "missed and search again for them (costs a call; "
                             "only ever ADDS files)")
    parser.add_argument("--json", action="store_true",
                        help="the bundle as JSON, for piping into another tool")
    parser.set_defaults(run=run, content=None)


def run(args: argparse.Namespace) -> str:
    """`--json` emits the CONTRACT, not a rendering of it: a caller piping
    this is writing against `contracts/`, the same shape MCP and HTTP serve."""
    bundle = search(args.path, args.query, path_filter=args.path_filter,
                    content=args.content, rerank=args.rerank, expand=args.expand)
    if args.json:
        return json.dumps(bundle, indent=2)
    return render(bundle, compact=not args.full, related_code=args.full)
