"""The CLI: parse, dispatch, and translate a failure into an exit code.

The commands themselves hold no argparse and no printing decisions beyond
their own output — they take parsed arguments and return text. That is what
lets the same behaviour be reached from MCP and HTTP without a second
implementation, and what keeps this file about the terminal.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from ..._errors import MegabrainError
from ..._version import __version__
from .commands import (
    ask,
    get,
    graph,
    index,
    install,
    scan,
    search,
    studio,
)

__all__ = ["main", "build_parser"]

_COMMANDS = (index, scan, search, ask, get, graph, studio, install)


def build_parser() -> argparse.ArgumentParser:
    """Every command registers its own flags. Adding one is a new module in
    `commands/`, never a branch here."""
    parser = argparse.ArgumentParser(
        prog="megabrain",
        description="Local code intelligence: one call returns all the code "
                    "related to a question.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    for module in _COMMANDS:
        module.register(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Exit codes: 0 fine, 1 an engine failure, 2 bad usage (argparse's own).

    A typed engine error prints ONE line naming what to do — a traceback is
    for the person who can fix the code, and the person reading this is trying
    to use the tool.
    """
    args = build_parser().parse_args(argv)
    try:
        output = args.run(args)
    except (MegabrainError, OSError) as err:
        # OSError too: a path that does not exist or cannot be read is an
        # ordinary mistake, and the person who made it wants one line, not a
        # traceback through the standard library.
        print(f"megabrain: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    if output:
        print(output)
    return 0


if __name__ == "__main__":       # `python -m megabrain.transports.cli.main`
    raise SystemExit(main())
