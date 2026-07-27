"""`megabrain graph` — what depends on what, in the terminal."""

from __future__ import annotations

import argparse
import json

from ....contracts import GraphMap, Neighbourhood
from ....graph import graph_map, graph_path, neighbourhood
from ._route import render_route

__all__ = ["register"]

SHOWN_PER_COMMUNITY = 6


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("graph", help="the import graph: clusters, hubs, paths")
    parser.add_argument("path", nargs="?", default=".",
                        help="anywhere inside the repo (default: .)")
    parser.add_argument("--node", metavar="FILE",
                        help="one file's dependencies, both directions")
    parser.add_argument("--from", dest="source", metavar="FILE",
                        help="with --to: how two files are connected")
    parser.add_argument("--to", dest="target", metavar="FILE")
    parser.add_argument("--no-labels", dest="label", action="store_false",
                        help="skip the cached model call that names the clusters")
    parser.add_argument("--code", action="store_true",
                        help="with --from/--to: show the code at each hop")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    if args.node:
        view = neighbourhood(args.path, args.node)
        return json.dumps(view, indent=2) if args.json else _render_node(view)
    if args.source or args.target:
        if not (args.source and args.target):
            raise ValueError("--from and --to go together")
        found = graph_path(args.path, args.source, args.target)
        return json.dumps(found, indent=2) if args.json else \
            render_route(found, code=args.code)
    whole = graph_map(args.path, label=args.label)
    return json.dumps(whole, indent=2) if args.json else _render_map(whole)


def _render_map(view: GraphMap) -> str:
    out = [f'# {view["repo"]} — {view["files"]} files · {len(view["links"])} '
           f'dependencies · {len(view["communities"])} clusters · {view["ms"]}ms',
           "\n## the core — where a change lands hardest"]
    out += [f'  {node["file"]:<44} {node["in_degree"]:>4} in · '
            f'{node["out_degree"]:>3} out · cluster {node["community"]}'
            for node in view["god_nodes"]]
    out.append("\n## clusters")
    for community in view["communities"]:
        head = ", ".join(community["files"][:SHOWN_PER_COMMUNITY])
        more = len(community["files"]) - SHOWN_PER_COMMUNITY
        out.append(f'  [{community["id"]}] {community["label"]} — '
                   f'{community["size"]} files: {head}'
                   + (f" … +{more}" if more > 0 else ""))
    return "\n".join(out + _render_surprises(view))


def _render_surprises(view: GraphMap) -> list[str]:
    """Last, and only when there are any: the finding nobody asked for."""
    if not view["surprises"]:
        return []
    return ["\n## twins that never met — similar code, no dependency",
            *(f'  {entry["score"]:.2f}  {entry["a"]}  ·  {entry["b"]}'
              for entry in view["surprises"])]


def _render_node(view: Neighbourhood) -> str:
    """Both directions, because "who imports this" is the half a reader cannot
    get by opening the file."""
    return "\n".join([
        f'# {view["file"]}  (cluster {view["community"]})',
        f'\nimports ({len(view["imports"])}):',
        *(f"  → {relpath}" for relpath in view["imports"]),
        f'\nimported by ({len(view["imported_by"])}):',
        *(f"  ← {relpath}" for relpath in view["imported_by"]),
    ])

