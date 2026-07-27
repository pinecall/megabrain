"""`megabrain get <file> [--symbol NAME]` — cash in a pointer from a bundle."""

from __future__ import annotations

import argparse
import json

from ....contracts import SymbolRef
from ....search.render import lang_of
from ....usecases import get_code

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("get", help="show one indexed file, or one symbol")
    parser.add_argument("file", help="repo-relative path, as a bundle prints it")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--symbol", metavar="NAME",
                        help="just this definition (bare name matches Class.name)")
    parser.add_argument("--outline", action="store_true",
                        help="the file's declarations only, no code")
    parser.add_argument("--json", action="store_true", help="the contract, as JSON")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    view = get_code(args.path, args.file, symbol=args.symbol)
    if args.json:
        return json.dumps(view, indent=2)
    header = [f'# {view["file"]} L{view["start_line"]}-{view["end_line"]}'
              + (f' · {view["symbol"]}' if view["symbol"] else "")]
    if view["stale"]:
        # Never silently served as current: these are the lines the ranking
        # saw, and the file has changed since.
        header.append("⚠ the file on disk has changed since it was indexed — "
                      "this is the INDEXED text · re-run `megabrain index`")
    if args.outline:
        return "\n".join([*header, "", *_outline(view["symbols"])])
    return "\n".join([*header, "", f'```{lang_of(view["file"])}',
                      view["text"], "```"])


def _outline(symbols: list[SymbolRef]) -> list[str]:
    return [f'{s["line"]:>6}  {s["signature"] or s["name"]}'
            + (f'  — {s["doc"]}' if s["doc"] else "")
            for s in symbols]
