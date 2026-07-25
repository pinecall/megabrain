"""What the narrator is asked when the request is a CHANGE.

Measured, asking a task the question-shaped way cost a whole extra round trip:
the narrator explained the mechanism and the agent came back with "donde esta
definido el helper redirect".

Three rules carry the weight. OPEN before proposing — the map names files, only
the file shows the region an edit lands in. CITE, never retype: a model that
types existing code back is a model that can quietly change it. And open
everything in ONE turn — a file per turn is a round trip per file, measured at
45% of the call.
"""

from __future__ import annotations

from ..contracts import Bundle
from ._anchorrules import ANCHOR_RULES
from ._taskwords import PROMPT

__all__ = ["build_task_prompt", "MAX_MAP_FILES"]

MAX_MAP_FILES = 20


def build_task_prompt(task: str, bundle: Bundle) -> str:
    """The map plus the instructions. Bodies are deliberately absent — the
    model pulls what it needs with `open_file`, which is what keeps a task
    about three files from carrying twenty files of code it will not touch."""
    lines: list[str] = []
    for entry in _files(bundle)[:MAX_MAP_FILES]:
        names = [str(s.get("name", "")) for s in (entry.get("symbols") or [])][:8]
        shown = ", ".join(n for n in names if n)
        lines.append(f"- {entry['file']}" + (f"  ({shown})" if shown else ""))
    # Substituted, never `.format()`. This prompt is mostly code-shaped text
    # and grows with every lesson; the first brace someone writes into it —
    # `end`/`}`/`)` in a rule about closing delimiters — turns every task call
    # into "Single '}' encountered in format string".
    return (PROMPT.replace("{anchor_rules}", ANCHOR_RULES)
                  .replace("{task}", task)
                  .replace("{map}", "\n".join(lines) or "- (nothing found)"))


def _files(bundle: Bundle) -> list[dict]:
    """CORE first, then RELATED — the ranking's own order, unaltered."""
    return [*bundle["tier1"], *bundle["tier2"]]      # type: ignore[list-item]
