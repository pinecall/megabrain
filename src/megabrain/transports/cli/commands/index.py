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
    parser.add_argument("--llm", action="store_true",
                        help="also write the mental map: one model-authored card "
                             "per file, so `megabrain brief` can answer "
                             "(costs a call per changed file)")
    parser.add_argument("--quiet", action="store_true", help="no progress output")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    """Progress goes to STDERR, the report to stdout.

    So `megabrain index . > report.txt` keeps the report clean while the
    person watching still sees movement — indexing a large repository is a
    long silence otherwise.
    """
    report = build_index(args.path, force=args.force, exclude=args.exclude,
                         llm=args.llm,
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
    parts += _study_lines(report)
    return "\n".join(parts)


def _study_lines(report: dict[str, object]) -> list[str]:
    """What the card pass did, or why it did nothing.

    The failure is printed, not swallowed: the index succeeded, so the exit
    code is 0, and a `--llm` run that wrote no cards has to say so or the next
    `brief` is a mystery.
    """
    if isinstance(failure := report.get("study_error"), str):
        return [f'  ⚠ no mental map: {failure}']
    if not isinstance(cards := report.get("study"), dict):
        return []
    return [f'  cards: {cards["written"]} written · {cards["unchanged"]} unchanged '
            f'· {cards["degraded"]} degraded · {cards["seconds"]}s '
            f'· model {cards["model"]}']


def _progress(event: dict[str, object]) -> None:
    if event["type"] == "file":
        line = f'  [{event["i"]}/{event["n"]}] {event["file"]}'
    elif event["type"] == "card":
        line = f'  card [{event["i"]}/{event["n"]}] {event["file"]}'
    else:
        line = f'  embedding {event["done"]}/{event["total"]}'
    print(f"\r\033[K{line[:110]}", end="", file=sys.stderr, flush=True)
