"""The verb `ask`: retrieve deterministically, then explain what was found.

The two halves are deliberately unequal. Retrieval is the product — no model,
milliseconds, and it decides WHAT the answer is built from. The model only
explains it, and cannot add code. So the bundle is emitted as an event before
any model runs: a caller that stops reading there still has the real answer.
"""

from __future__ import annotations

from pathlib import Path

from .._errors import MissingCredential
from .._types import Content
from ..ask.events import Emit, emit_nothing
from ..ask.narrator import narrate
from ..project import load_project
from ..providers.chat import ChatProvider, OpenAICompatible
from ._root import resolve_root
from .search import search

__all__ = ["ask"]


def ask(start: Path | str, question: str, *, path_filter: str | None = None,
        content: Content | None = "code", emit: Emit = emit_nothing) -> str:
    """A narrated walkthrough of the code that answers `question`.

    `content` defaults to CODE, unlike search: a code walkthrough diluted with
    prose explains the documentation instead of the mechanism. A caller that
    wants the docs narrated asks for them.
    """
    bundle = search(start, question, path_filter=path_filter, content=content)
    emit({"type": "retrieval", "repo": bundle["repo"], "ms": bundle["ms"],
          "core": [entry["file"] for entry in bundle["tier1"]],
          "related": len(bundle["tier2"])})
    provider = _narrator(start)
    if provider is None:
        # Named, not a generic failure: retrieval already worked, and the only
        # thing missing is a credential the message can point at.
        raise MissingCredential.named("MEGABRAIN_CHAT_API_KEY")
    return narrate(provider, question, bundle, emit=emit)


def _narrator(start: Path | str) -> ChatProvider | None:
    """The model the REPOSITORY chose to narrate with.

    Per project, not per shell: `.megabrain.json` is committed, so everyone
    working on that repo gets the same walkthroughs.
    """
    provider = OpenAICompatible(model=load_project(resolve_root(start)).narrator_model)
    return provider if provider.available() else None
