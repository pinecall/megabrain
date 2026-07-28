"""`megabrain.json` — what a REPOSITORY decides about itself.

One file, checked in, holding what used to live in two dotfiles and four
environment variables: which paths to skip, the questions the repo wants asked
of it, and which models narrate and judge.

    {
      "ignore":  ["dist", "vendor/**"],
      "gitignore": true,
      "queries": ["how does the retry policy work?"],
      "models":  {"provider": "claude",
                  "narrator": "google/gemini-3.1-flash-lite",
                  "rerank":   "google/gemini-3.5-flash-lite"}
    }

The precedence is deliberate: an explicit argument beats the file, the file
beats the environment, the environment beats the built-in default. A project's
config TRAVELS — it is committed, and the next person to clone gets it — while
an env var lives in one shell and is invisible to everyone else, which is how a
repo ends up indexed differently by two people on the same team.

Nothing here is required. A repository with no config is fully usable, a
malformed one falls back and says so, and a field of the wrong shape is ignored
on its own without taking the rest of the file down.

VISIBLE, not a dotfile, and that is the point: this file is committed and meant
to be found and edited by whoever clones the repo, while `.megabrain/` beside
it is machine state nobody reads. The dot marks what you ignore.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ._config_file import lines_of, read_object, string_map, string_tuple
from ._models import NARRATOR_MODEL, RERANK_MODEL

CONFIG_FILE = "megabrain.json"
LEGACY_IGNORE = ".megabrainignore"
LEGACY_QUERIES = ".megabrainqueries"

__all__ = ["Project", "load_project", "CONFIG_FILE"]


@dataclass(frozen=True, slots=True)
class Project:
    """One repository's configuration, already resolved."""

    root: Path
    ignore: tuple[str, ...] = ()
    queries: tuple[str, ...] = ()
    gitignore: bool = True
    """Whether `.gitignore` also decides what is not source. Default TRUE.

    True is right for the repos that made the case — shipway's `bin/`, aldus's
    `dist-lib-types/`, sdk's `src.bkp/` are build output and dead snapshots that
    the repo already declared. But it is a heuristic with a real false positive,
    found in megabrain-v2 itself: `evals/` is gitignored and IS source. So the
    escape is a committed field rather than a flag, because whoever hits this
    knows their repo and the next person to clone it should inherit the answer.
    """
    narrator_model: str = NARRATOR_MODEL
    rerank_model: str = RERANK_MODEL
    chat_provider: str = ""
    """Which backend EVERY model lane uses: `claude` for the Agent SDK, else
    the OpenAI-compatible endpoint. Empty = nobody chose, the endpoint wins.
    Committed in `models.provider` so the whole team narrates on one lane."""
    malformed: bool = False
    """True when a config file exists but could not be read.

    Reported rather than swallowed: silently falling back looks identical to
    having no config, and somebody edited that file expecting it to matter.
    """


def load_project(root: Path | str) -> Project:
    """Read `<root>/megabrain.json`, merged with the legacy dotfiles."""
    base = Path(root).expanduser()
    raw, malformed = read_object(base / CONFIG_FILE)
    models = string_map(raw.get("models"))
    return Project(
        root=base,
        ignore=(*string_tuple(raw.get("ignore")), *lines_of(base / LEGACY_IGNORE)),
        queries=(*string_tuple(raw.get("queries")), *lines_of(base / LEGACY_QUERIES)),
        # Only an explicit `false` turns it off: a missing key and a malformed
        # one both have to mean the default, or a typo would silently widen the
        # index back out with nothing to show that it had.
        gitignore=raw.get("gitignore") is not False,
        narrator_model=models.get("narrator")
        or os.environ.get("MEGABRAIN_ASK_MODEL") or NARRATOR_MODEL,
        rerank_model=models.get("rerank")
        or os.environ.get("MEGABRAIN_RERANK_MODEL") or RERANK_MODEL,
        chat_provider=(models.get("provider")
                       or os.environ.get("MEGABRAIN_CHAT_PROVIDER")
                       or "").strip().lower(),
        malformed=malformed)
