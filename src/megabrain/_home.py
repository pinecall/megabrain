"""Where machine-global state lives: the embedding cache and the repo registry.

One function, so there is exactly one answer. It also makes the location
INJECTABLE, which is what keeps a test suite from writing into the developer's
real home directory — a suite that pollutes `$HOME` is one nobody trusts to run
twice.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["megabrain_home", "HOME_VAR"]

HOME_VAR = "MEGABRAIN_HOME"


def megabrain_home() -> Path:
    """`$MEGABRAIN_HOME`, or `~/.megabrain`.

    Not created here: a read should not have the side effect of making
    directories, and every writer already creates what it needs.
    """
    return Path(os.environ.get(HOME_VAR) or Path.home() / ".megabrain")
