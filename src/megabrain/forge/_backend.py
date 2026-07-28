"""Which model writes the code, and how its reply becomes a module.

Separate from the orchestrator because it is the only part that touches a
provider: everything else in the coverage forge is deterministic, and tests
inject a fake `generate` precisely so none of this runs offline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

__all__ = ["Generate", "backend_generate", "extract_code",
           "MAX_GEN_TOKENS", "GEN_TIMEOUT"]

MAX_GEN_TOKENS = 6000
GEN_TIMEOUT = 180.0

Generate = Callable[[str], str]


def backend_generate(base: Path, model: str | None) -> Generate:
    """prompt -> raw model text, through the repository\'s chat backend.

    Loud without a credential — the caller explicitly asked to forge, and a
    silent no-op would read as "nothing to forge".
    """
    import os

    from .._provider_errors import MissingCredential
    from ..project import load_project
    from ..providers.chat import resolve

    project = load_project(base)
    chosen = (model or os.environ.get("MEGABRAIN_FORGE_MODEL")
              or project.narrator_model)
    provider = resolve(model=chosen, timeout=GEN_TIMEOUT,
                       provider=project.chat_provider)
    if provider is None:
        raise MissingCredential.named("MEGABRAIN_CHAT_API_KEY")
    return lambda prompt: provider.chat_text(chosen, prompt,
                                             max_tokens=MAX_GEN_TOKENS)


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (match.group(1) if match else text).strip() + "\n"
