"""The two things a person reads: what was found, and what was done."""

from __future__ import annotations

from ...contracts.install import HostResult, HostRow
from ..mcp.tools import TOOLS

__all__ = ["render", "render_detected"]

_DONE = ("registered", "removed")


def render(results: list[HostResult], remove: bool = False) -> str:
    """The report. Every host gets a line, including the skipped ones — a list
    that only shows successes cannot answer "why isn't Cursor in there"."""
    lines = [f'  {"✓" if row["action"] in _DONE else "·"} {row["label"]:<12} '
             f'{row["action"]:<24} {row["path"]}' for row in results]
    done = [row for row in results if row["action"] in _DONE]
    verb = "Unregistered" if remove else "Registered"
    head = (f"{verb} megabrain in {len(done)} platform(s):" if done
            else "No platforms touched.")
    return head + "\n" + "\n".join(lines) + _tail(bool(done) and not remove)


def _tail(worth_saying: bool) -> str:
    """The one instruction that is not obvious: a running assistant has already
    read its config, so nothing happens until it is restarted."""
    if not worth_saying:
        return ""
    return ("\n\nRestart your assistant to pick it up. Tools: "
            + ", ".join(tool.name for tool in TOOLS) + ".")


def render_detected(rows: list[HostRow]) -> str:
    """`--list`: the same table, changing nothing.

    Three states, not two: a product that is absent, one that is here but
    unregistered, and one already wired up. Collapsing the first two would send
    someone to install an editor they already have.
    """
    lines = ["Detected AI coding assistants on this machine:"]
    for row in rows:
        state = ("registered" if row["registered"] else
                 "not registered" if row["installed"] else "not installed")
        lines.append(f'  {"✓" if row["installed"] else "·"} {row["label"]:<12} '
                     f'{state:<16} {row["path"]}')
    return "\n".join(lines)
