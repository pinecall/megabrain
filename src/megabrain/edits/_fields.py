"""Reading one operation, however the caller happened to spell it.

FIELD RUN (attrs#1549), and it is why this module exists rather than a direct
`op["file"]`: an agent called replace with `{path, old, new}` — the host's own
Edit uses `old_string`/`new_string`, so the habit is well earned — and the call
failed as "path escapes the repo: ''", because the missing key produced an
empty string that was then resolved as a path. The error named the wrong thing
entirely, and the caller had no way to see the real problem.

Canonical names are file / find / replace. The aliases people actually type are
accepted, and a genuinely absent field NAMES ITSELF.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

__all__ = ["field", "safe_path", "FILE", "FIND", "REPLACE"]

FILE = ("file", "path", "filename")
FIND = ("find", "old", "old_string", "search")
REPLACE = ("replace", "new", "new_string", "with")


def field(op: Mapping[str, Any], *names: str) -> str:
    """The first alias actually present, as text. Absent -> "" ."""
    for name in names:
        value = op.get(name)
        if value is not None:
            return str(value)
    return ""


def safe_path(root: Path, relpath: str) -> Path:
    """`relpath` inside `root`, or a refusal.

    Resolved before the check, not after: `a/../../etc` only reveals where it
    points once it is normalised, and a prefix test on the raw string passes it.
    """
    root = root.resolve()
    target = (root / relpath).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes the repo: {relpath!r}")
    return target
