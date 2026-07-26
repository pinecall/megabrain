"""`megabrain install` — put the MCP server in every assistant on this box."""

from __future__ import annotations

import argparse

from ...install import PLATFORMS, apply, detect, render, render_detected

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser(
        "install", help="register the MCP server with your AI coding assistants "
                        "(Claude Code, Codex, Antigravity, Cursor, Windsurf, "
                        "Gemini CLI) — detected automatically")
    parser.add_argument("--platform", choices=sorted(PLATFORMS), metavar="NAME",
                        help=f"only this one ({', '.join(sorted(PLATFORMS))}); "
                             "default: every platform detected")
    parser.add_argument("--list", action="store_true", dest="list_only",
                        help="show what's detected and where, change nothing")
    parser.add_argument("--remove", action="store_true",
                        help="unregister megabrain instead of registering it")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    """`--platform` is an argparse `choices`, so an unknown name exits 2 with
    argparse's own message rather than reaching the engine — the API still
    raises for a caller that bypasses the CLI."""
    if args.list_only:
        return render_detected(detect())
    return render(apply(platform=args.platform, remove=args.remove),
                  remove=args.remove)
