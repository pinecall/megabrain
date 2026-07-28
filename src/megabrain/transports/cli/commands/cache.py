"""`megabrain cache [prune]` — see the embedding cache, and shrink it on purpose.

The cache is content-addressed and never expires on its own: every model ever
pointed at keeps its full corpus of vectors until somebody asks. Automatic
eviction was rejected outright — deleting cache during an index is how you pay
for the same vectors twice — so the sweep is a command, and the default action
only measures.
"""

from __future__ import annotations

import argparse

from ....providers.embeddings import EmbedCache

__all__ = ["register"]

DEFAULT_DAYS = 90.0


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("cache", help="embedding cache: size, and prune")
    parser.add_argument("action", nargs="?", choices=["prune"],
                        help="omit to just report the size")
    parser.add_argument("--older-than", type=float, default=DEFAULT_DAYS,
                        metavar="DAYS", help="prune entries untouched for DAYS "
                        f"(default: {DEFAULT_DAYS:.0f})")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    cache = EmbedCache()
    if args.action == "prune":
        removed, freed = cache.prune(older_than_days=args.older_than)
        return (f"pruned {_counted(removed)} ({_sized(freed)}) untouched for "
                f"{args.older_than:.0f}+ days from {cache.root}")
    entries, size = cache.size()
    return (f"{cache.root}: {_counted(entries)}, {_sized(size)}"
            + ("" if not entries else
               "  — `megabrain cache prune` sweeps stale ones"))


def _counted(entries: int) -> str:
    return f"{entries} vector" + ("" if entries == 1 else "s")


def _sized(size: int) -> str:
    if size >= 1 << 20:
        return f"{size / (1 << 20):.1f} MB"
    return f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
