"""`megabrain ask` — the narrated walkthrough, streamed to the terminal."""

from __future__ import annotations

import argparse
import sys
from typing import cast

from ....ask.ask import ask
from ....ask.events import Event

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("ask", help="a walkthrough of the code that answers a question")
    parser.add_argument("question", help="the question, in plain words")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--path-filter", metavar="PREFIX", help="only files under PREFIX")
    parser.add_argument("--docs", dest="content", action="store_const", const="docs",
                        help="narrate the prose instead of the code")
    parser.add_argument("--quiet", action="store_true",
                        help="the walkthrough only, no retrieval trace")
    parser.set_defaults(run=run, content="code")


def run(args: argparse.Namespace) -> str:
    """Deltas go to STDOUT as they arrive; the trace goes to stderr.

    So `megabrain ask … > answer.md` keeps the file clean while the person
    watching still sees which files were retrieved — and sees them BEFORE the
    model has said anything, because that part is already the real answer.
    """
    written = _Live(quiet=args.quiet)
    ask(args.path, args.question, path_filter=args.path_filter,
        content=args.content, emit=written)
    print()
    return ""


class _Live:
    """Prints deltas as they land, and the trace on the side."""

    def __init__(self, *, quiet: bool) -> None:
        self.quiet = quiet

    def __call__(self, event: Event) -> None:
        kind = event.get("type")
        if kind == "delta":
            print(event.get("text", ""), end="", flush=True)
        elif not self.quiet:
            print(_trace(event), file=sys.stderr, flush=True)


def _trace(event: Event) -> str:
    kind = event.get("type")
    if kind == "retrieval":
        core = cast("list[str]", event.get("core") or [])
        return (f'· retrieved in {event.get("ms")}ms — '
                f'{len(core)} core, {event.get("related")} related: '
                + ", ".join(core))
    if kind == "narrating":
        return f'· narrating over {event.get("candidates")} chunks…'
    if kind == "opened":
        return f'· opened {event.get("file")} ({event.get("chars")} chars)'
    if kind == "narrated":
        return f'\n· done in {event.get("ms")}ms'
    return f'· {kind}'
