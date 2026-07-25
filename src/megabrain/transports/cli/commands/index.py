"""`megabrain index [path]` — build or update a repository's index."""

from __future__ import annotations

import argparse
import sys

from ....usecases import build_index

__all__ = ["register"]


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("index", help="index or update a repository")
    parser.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    parser.add_argument("--force", action="store_true",
                        help="re-chunk and re-embed every file, ignoring hashes")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="skip paths matching GLOB (repeatable)")
    parser.add_argument("--quiet", action="store_true", help="no progress output")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    """Progress goes to STDERR, the report to stdout.

    So `megabrain index . > report.txt` keeps the report clean while the
    person watching still sees movement — indexing a large repository is a
    long silence otherwise.
    """
    report = build_index(args.path, force=args.force, exclude=args.exclude,
                         on_progress=None if args.quiet else _progress)
    if not args.quiet:
        print(file=sys.stderr)
    return _summary(report)


def _summary(report: dict[str, object]) -> str:
    parts = [f'{report["repo"]}: {report["files"]} files · {report["chunks"]} chunks '
             f'· {report["edges"]} edges · {report["seconds"]}s',
             f'  {report["changed"]} changed · {report["unchanged"]} unchanged '
             f'· {report["removed"]} removed · {report["skipped"]} skipped']
    if report["partition_violations"]:
        # Silence here would mean chunks that do not cover their file — the one
        # invariant the chunker cannot be wrong about without losing code.
        parts.append(f'  ⚠ {report["partition_violations"]} partition violation(s)')
    return "\n".join(parts)


def _progress(event: dict[str, object]) -> None:
    if event["type"] == "file":
        line = f'  [{event["i"]}/{event["n"]}] {event["file"]}'
    elif event["type"] == "card":
        line = f'  card [{event["i"]}/{event["n"]}] {event["file"]}'
    else:
        line = f'  embedding {event["done"]}/{event["total"]}'
    print(f"\r\033[K{line[:110]}", end="", file=sys.stderr, flush=True)
