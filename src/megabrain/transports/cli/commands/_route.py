"""Rendering a route in the terminal.

The route is the one graph view whose value is entirely in the annotation: the
filenames are the least of it. So each hop names the edge it crossed, the
symbols that carry it, and — asked for — the real code on both sides.

A route that is a MEETING rather than a chain says so on its own line, because
that is precisely the case where an indented arrow diagram reads like a flow
that does not exist.
"""

from __future__ import annotations

from ....contracts import CodeSnip, GraphPath, Hop

__all__ = ["render_route"]


def render_route(view: GraphPath, *, code: bool = False) -> str:
    if not view["found"]:
        return f'no path between {view["source"]} and {view["target"]}'
    out: list[str] = []
    if view["flipped"]:
        out.append("# shown in call-flow order (the calls run this way)\n")
    for step, hop in enumerate(view["hops"]):
        out.append(_hop_line(step, hop))
        if code and hop.get("code"):
            out += _code_lines(hop["code"])          # type: ignore[arg-type]
    return "\n".join(out + _shape(view))


def _hop_line(step: int, hop: Hop) -> str:
    arrow = "└→ " if step else ""
    tail = f'  [{hop["via"]}]' if hop.get("via") else ""
    carriers = hop.get("symbols") or []
    return (f'{"  " * step}{arrow}{hop["file"]}{tail}'
            + (f'  · {", ".join(carriers)}' if carriers else ""))


def _code_lines(code: dict[str, object]) -> list[str]:
    out: list[str] = []
    for role in ("use", "definition"):
        snip = code.get(role)
        if isinstance(snip, dict):
            out += _snip_lines(role, snip)  # type: ignore[arg-type]
    if not code["verified"]:
        out.append("      (inferred: the receiver's type is not known here)")
    return out


def _snip_lines(role: str, snip: CodeSnip) -> list[str]:
    where = snip.get("in_symbol")
    head = (f'      {role} · {snip["file"]}:{snip["start_line"]}'
            + (f" in {where}()" if where else ""))
    marked = set(snip.get("hi_rows") or ())
    body = [f'      {">" if index in marked else " "} {line}'
            for index, line in enumerate(snip["text"].splitlines())]
    return [head, *body, ""]


def _shape(view: GraphPath) -> list[str]:
    """Whether this is a chain at all — the honest footer.

    Presented without it, `scoring → http ← rerank` reads as "scoring reaches
    rerank through http", which is a relationship the code does not have.
    """
    if view["chain"] or not view["meet"]:
        return []
    both = ("both ends call into it" if view["meet_kind"] == "callee"
            else "it calls both ends")
    return [f'\n! not a call chain: the two files MEET at {view["meet"]} — {both}']
