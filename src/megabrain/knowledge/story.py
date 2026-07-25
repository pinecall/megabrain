"""A route, told truthfully.

Routing produces files and edge kinds. This turns that into something a reader
can follow — the carrier symbols, the real code at both ends of each hop — and
guards the two ways the telling can lie: presenting a route against the call
flow, and presenting a shared callee as if it were a chain.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import Hop
from ..storage import Store
from .carriers import hop_code, hop_symbols

__all__ = ["tell", "orient_hops"]


def tell(store: Store, root: Path | str, hops: list[Hop]) -> dict[str, object]:
    """Annotate a route and diagnose its shape."""
    told, flipped = orient_hops(store, hops)
    for step in range(1, len(told)):
        previous, current = told[step - 1]["file"], told[step]["file"]
        symbols = hop_symbols(store, root, previous, current)
        told[step]["symbols"] = symbols
        told[step]["code"] = hop_code(store, root, previous, current, symbols)
    meet, meet_kind = _meeting(told)
    return {"hops": told, "flipped": flipped, "chain": meet is None,
            "meet": meet, "meet_kind": meet_kind}


def orient_hops(store: Store, hops: list[Hop]) -> tuple[list[Hop], bool]:
    """Present the route in CALL-FLOW order, and say whether it was flipped.

    Flipped ONLY when the whole route runs against the asked order. A mixed
    route is not a chain in either direction, so reversing it would trade one
    wrong story for another while disrespecting the question as it was asked.
    """
    if len(hops) < 2:
        return hops, False
    edges = {(source, target) for source, target, _ in store.graph.all_edges()}
    forward = backward = 0
    for step in range(1, len(hops)):
        pair = (hops[step - 1]["file"], hops[step]["file"])
        forward += pair in edges
        backward += pair[::-1] in edges
    if forward or not backward:
        return hops, False
    return _reversed(hops), True


def _reversed(hops: list[Hop]) -> list[Hop]:
    """Reverse the walk, carrying each `via` with the edge it describes.

    A hop's `via` names the edge ENTERING it. Reversing the list without moving
    the labels one place along would attribute every edge to the wrong hop.
    """
    last = len(hops) - 1
    flipped: list[Hop] = []
    for step in range(len(hops)):
        via = hops[last - step + 1]["via"] if step else ""
        flipped.append(Hop(file=hops[last - step]["file"], via=via))
    return flipped


def _meeting(hops: list[Hop]) -> tuple[str | None, str | None]:
    """Where the two ends actually meet, when the route is not a chain.

    Each hop's direction comes from which side its evidence put the definition
    on. A route that runs forward and then backward is `a → M ← b`: both ends
    call INTO the middle. The reverse is `a ← M → b`: the middle calls both.
    """
    directions = [_direction(hops[step]) for step in range(1, len(hops))]
    known = [step for step in directions if step]
    if not ("fwd" in known and "back" in known):
        return None, None
    for index in range(len(directions) - 1):
        pair = (directions[index], directions[index + 1])
        if pair == ("fwd", "back"):
            return hops[index + 1]["file"], "callee"
        if pair == ("back", "fwd"):
            return hops[index + 1]["file"], "caller"
    return None, None


def _direction(hop: Hop) -> str | None:
    """"fwd" when this hop's file DEFINES the carrier, "back" when it uses it,
    None when the hop has no evidence to read a direction from."""
    code = hop.get("code") or {}
    use, definition = code.get("use"), code.get("definition")
    if not use or not definition:
        return None
    return "fwd" if definition.get("file") == hop["file"] else "back"
