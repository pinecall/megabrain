"""The brief as terminal markdown — prose first, relations as arrows, bodies
deliberately absent: they live one `megabrain get` away, and the point of a
brief is to be readable in one screen."""

from __future__ import annotations

from ..contracts import Brief

__all__ = ["render_brief"]

_RELATION_CAP = 10       # relations named before "+n more"


def render_brief(brief: Brief) -> str:
    lines = [f'# brief — "{brief["query"]}"',
             f'repo {brief["repo"]} · {len(brief["files"])} files of '
             f'{brief["considered"]} · {brief["ms"]}ms · 0 llm calls', ""]
    for entry in brief["files"]:
        flag = " · degraded card (skeleton only)" if entry["degraded"] else ""
        lines.append(f'## {entry["file"]}{flag}')
        lines.append(entry["card"])
        if entry["imports"]:
            lines.append(f'  → uses: {_capped(entry["imports"])}')
        if entry["imported_by"]:
            lines.append(f'  ← used by: {_capped(entry["imported_by"])}')
        for symbol in entry["symbols"]:
            lines.append(f'    · {symbol["signature"] or symbol["name"]}')
        lines.append("")
    lines.append("── bodies live one call away: megabrain get <file> [--symbol <name>]")
    return "\n".join(lines)


def _capped(items: list[str], cap: int = _RELATION_CAP) -> str:
    extra = len(items) - cap
    shown = ", ".join(items[:cap])
    return f"{shown} (+{extra} more)" if extra > 0 else shown
