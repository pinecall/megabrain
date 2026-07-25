"""The verb `study`: a model reads the index and writes the mental map.

The expensive half of the atlas, run deliberately and rarely — cards are
cached by skeleton, so a re-study after normal body-editing work writes
almost nothing.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .._provider_errors import MissingCredential
from ..atlas import write_cards
from ..project import load_project
from ..providers.chat import ChatProvider, OpenAICompatible
from ..storage import Store
from ..storage.locate import resolve_root

__all__ = ["study"]

Progress = Callable[[dict[str, object]], None]


def study(start: Path | str, *, model: str | None = None, force: bool = False,
          provider: ChatProvider | None = None,
          on_progress: Progress | None = None) -> dict[str, object]:
    """Write or refresh the repo's cards and report what happened.

    The model comes from `megabrain.json`'s `models.study` (or
    `MEGABRAIN_STUDY_MODEL`), which is its own knob rather than the narrator's:
    study spends one call per FILE, so the tier that is a rounding error for a
    single walkthrough is the whole bill here.

    Unlike the judge lane this verb does NOT fail open on a missing provider:
    someone asked for cards, and silently writing none would report success
    about work that never happened.
    """
    root = resolve_root(start)
    chosen = model or load_project(root).study_model
    active = provider or OpenAICompatible(model=chosen)
    if not active.available():
        raise MissingCredential(
            "no chat provider is configured — set your chat API key so "
            "`megabrain study` can write the cards")
    started = time.perf_counter()
    with Store(root) as store:
        stats = write_cards(store, active, chosen,
                            force=force, on_progress=on_progress)
    return {**stats, "repo": root.name, "model": chosen,
            "seconds": round(time.perf_counter() - started, 2)}
