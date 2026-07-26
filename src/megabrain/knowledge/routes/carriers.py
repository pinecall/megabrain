"""The symbols that carry a hop, and the code that proves it.

A route of filenames is a claim with no evidence behind it. What a reader wants
at every hop is the function that connects the two files, the place it is
called, and the place it is defined — and all three have to be real, or the
route is a story the graph made up.
"""

from __future__ import annotations

from pathlib import Path

from ...contracts import HopCode
from ...storage import Store
from ..symbols.snips import enclosing_symbol, snip_at
from ..symbols.usesites import use_sites

__all__ = ["hop_symbols", "hop_code", "CARRIER_CAP", "MIN_NAME"]

CARRIER_CAP = 4
MIN_NAME = 3
"""One- and two-letter names collide with everything, so the evidence they give
is worth less than the noise they add."""

CALLABLE_KINDS = frozenset({"class", "function", "async_function", "method",
                            "async_method", "interface", "type", "enum"})


def hop_symbols(store: Store, root: Path | str, one: str, two: str) -> list[str]:
    """Names defined in one file of the pair and ACTUALLY used in the other.

    Both directions, since a route walks edges undirected and the definition
    can sit on either end. Verified carriers rank first, then by use count,
    then by name so the order never wobbles between runs.
    """
    scored: dict[str, tuple[int, bool]] = {}
    for defs_file, uses_file in ((two, one), (one, two)):
        names = _callables(store, defs_file)
        if not names:
            continue
        for name, site in use_sites(store, root, uses_file, names, defs_file).items():
            count, verified = scored.get(name, (0, False))
            scored[name] = (count + max(1, len(site.lines)),
                            verified or site.verified)
    ranked = sorted(scored.items(),
                    key=lambda kv: (not kv[1][1], -kv[1][0], kv[0]))
    return [name for name, _ in ranked][:CARRIER_CAP]


def hop_code(store: Store, root: Path | str, one: str, two: str,
             symbols: list[str]) -> HopCode | None:
    """Use and definition snippets for the first carrier that has both.

    Which side defines and which side uses is discovered, not assumed: the
    route is undirected, so the edge may run either way and the snippets have
    to follow the code rather than the walk.
    """
    for symbol in symbols:
        for defs_file, uses_file in ((two, one), (one, two)):
            found = _pair(store, root, symbol, defs_file, uses_file)
            if found is not None:
                return found
    return None


def _pair(store: Store, root: Path | str, symbol: str, defs_file: str,
          uses_file: str) -> HopCode | None:
    declared = next((entry for entry in store.symbols.read_for(defs_file)
                     if str(entry["name"]).rsplit(".", 1)[-1] == symbol), None)
    if declared is None:
        return None
    site = use_sites(store, root, uses_file, {symbol}, defs_file).get(symbol)
    lines = site.lines if site else []
    use = snip_at(store.chunks.read_file(uses_file), symbol, at_lines=lines)
    if use is not None and lines:
        use["in_symbol"] = enclosing_symbol(store.symbols.read_for(uses_file), lines[0])
    definition = snip_at(store.chunks.read_file(defs_file), symbol,
                         at_line=int(declared["line"] or 1))
    if use is None and definition is None:
        return None
    return HopCode(symbol=symbol, verified=bool(site and site.verified),
                   use=use, definition=definition)


def _callables(store: Store, relpath: str) -> set[str]:
    return {name for entry in store.symbols.read_for(relpath)
            if entry["kind"] in CALLABLE_KINDS
            if len(name := str(entry["name"] or "").rsplit(".", 1)[-1]) >= MIN_NAME}
