"""What the repository itself already said is not its source: `.gitignore`.

MEASURED across the machine's indexed repos, and it was the single largest source
of noise in a render. shipway compiles TypeScript into `bin/`, which `.gitignore`
declares under "# Build output" — and 122 of its 196 indexed files were that
output, so every symbol in `src/` had a compiled twin and a `grep` for one site
returned two. aldus contributed `dist-demo/` and `dist-lib-types/*.d.ts`;
pinecall/sdk contributed `src.bkp/`, a snapshot of old code competing with the
live version, which is the worst kind: it looks exactly like an answer.

`Excluder` cannot cover this. Its list is universal on purpose (`dist`, `build`,
`node_modules`) because baking one project's quirks into it applies them to every
repository on the machine — and `bin/` is where a Python or Rust project keeps
real code. The repo already answered the question for its own layout; nothing
here has to guess.

Delegated to `git check-ignore` rather than reading the file: gitignore has
negation (`!keep.js`), `**`, per-directory files, `.git/info/exclude` and the
user's global ignore, and a half-implementation of those silently drops files
nobody meant to drop. One process for the whole candidate list.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

__all__ = ["git_ignored", "TIMEOUT"]

TIMEOUT = 30
"""Seconds `git check-ignore` may take before it is abandoned.

Fails OPEN — a hung or missing git yields an empty set and indexing proceeds
with everything, which is the behaviour this file changed. Losing the filter
costs precision; losing the index costs the tool."""


def git_ignored(root: Path, relpaths: Sequence[str]) -> frozenset[str]:
    """The subset of `relpaths` this repo's git ignores. Empty if git cannot say.

    Empty on every failure — not a git repository, git not installed, a timeout.
    A precision filter must never be able to stop an index from being built.
    """
    if not relpaths or not (root / ".git").exists():
        return frozenset()
    try:
        done = subprocess.run(
            ["git", "check-ignore", "--stdin"], cwd=root,
            input="\n".join(relpaths), capture_output=True, text=True,
            timeout=TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    # Exit 1 means "nothing matched" and is the normal answer for a clean repo;
    # only 0 and 1 carry a usable verdict. Anything else (128: not a work tree)
    # is a failure whose stdout must not be read as a list of files to drop.
    if done.returncode not in (0, 1):
        return frozenset()
    return frozenset(line.strip() for line in done.stdout.splitlines() if line.strip())
