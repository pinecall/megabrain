"""Which model narrates FOR THIS REPOSITORY — resolved once, shared by verbs.

Per project, not per shell: `megabrain.json` is committed, so everyone working
on that repo gets the same walkthroughs. Routed through the provider registry
rather than constructing one backend by name — which is the whole point of
having a registry, and was the reason `resolve` shipped with no caller: adding
the SDK lane here would otherwise have meant an if-switch in every verb.
"""

from __future__ import annotations

from pathlib import Path

from ..project import load_project
from ..providers.chat import ChatProvider, resolve

__all__ = ["narrator_for"]


def narrator_for(root: Path) -> ChatProvider | None:
    """The chat backend the repository chose, or None without a credential."""
    project = load_project(root)
    return resolve(model=project.narrator_model, provider=project.chat_provider)
