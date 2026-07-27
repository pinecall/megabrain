"""`megabrain grep` — where to look, for a change you are about to make."""

from __future__ import annotations

import argparse
import sys

from ....ask.events import Event
from ....grep.grep import grep

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser(
        "grep", help="the files and symbols a change has to touch, with line ranges")
    parser.add_argument("task", help="the change you are about to make")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--path-filter", metavar="PREFIX", help="only files under PREFIX")
    parser.add_argument("--why", action="store_true",
                        help="one model call: adds a note per site, and the site "
                             "no literal search can reach (measured: 0.05s -> 1.3s)")
    parser.add_argument("--quiet", action="store_true",
                        help="the sites only, no retrieval trace")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    """The rows go to STDOUT, the trace to stderr — so `| grep` and `> file`
    both stay clean while the person watching still sees what was retrieved."""
    grep(args.path, args.task, path_filter=args.path_filter, why=args.why,
         emit=_Live(quiet=args.quiet))
    return ""


class _Live:
    def __init__(self, *, quiet: bool) -> None:
        self.quiet = quiet

    def __call__(self, event: Event) -> None:
        if event.get("type") == "delta":
            print(event.get("text", ""), flush=True)
        elif not self.quiet:
            print(f'· {event.get("type")}', file=sys.stderr, flush=True)
