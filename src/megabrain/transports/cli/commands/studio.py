"""`megabrain studio` — the UI and its API on one port."""

from __future__ import annotations

import argparse
import os
import sys

from ...http import Policy, bound_port, build_server

__all__ = ["register"]

DEFAULT_PORT = 2137


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = sub.add_parser("studio", help="serve the studio UI and the JSON API")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=os.environ.get("MEGABRAIN_API_TOKEN", ""),
                        help="require `Authorization: Bearer <token>` "
                             "($MEGABRAIN_API_TOKEN)")
    parser.add_argument("--readonly", action="store_true",
                        help="serve queries but refuse to index — for a public box")
    parser.add_argument("--rate-limit", type=int, default=0, metavar="N",
                        help="at most N requests per minute per caller")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> str:
    """Blocks until interrupted. The banner goes to stderr so it stays visible
    when stdout is redirected."""
    policy = Policy(token=args.token, readonly=args.readonly,
                    rate_limit=args.rate_limit)
    server = build_server(args.host, args.port, policy)
    print(f"megabrain studio → http://{args.host}:{bound_port(server)}/"
          + ("  (token required)" if args.token else ""), file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass                    # Ctrl-C is how this is meant to end
    finally:
        server.server_close()
    return ""
