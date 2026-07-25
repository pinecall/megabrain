"""`megabrain study [path]` — have a model write the repo's mental map."""

from __future__ import annotations

import argparse
import sys

from ....usecases import study

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser(
        "study", help="write the mental map: one model-authored card per file "
                      "(cached — re-runs only touch changed interfaces)")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--model", help="chat model for the cards "
                                        "(default: the repo's narrator model)")
    parser.add_argument("--force", action="store_true",
                        help="rewrite every card, ignoring the cache")
    parser.add_argument("--quiet", action="store_true", help="no progress output")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    report = study(args.path, model=args.model, force=args.force,
                   on_progress=None if args.quiet else _progress)
    if not args.quiet:
        print(file=sys.stderr)
    return (f'{report["repo"]}: {report["written"]} cards written · '
            f'{report["unchanged"]} unchanged · {report["degraded"]} degraded · '
            f'{report["skipped"]} skipped (nothing declared) · '
            f'{report["seconds"]}s · model {report["model"]}')


def _progress(event: dict[str, object]) -> None:
    line = f'  [{event["i"]}/{event["n"]}] {event["file"]}'
    print(f"\r\033[K{line[:110]}", end="", file=sys.stderr, flush=True)
