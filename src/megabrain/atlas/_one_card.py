"""One card: the prompt, the oracle gate, the one retry, the degrade.

The whole per-file story, kept away from the pass that runs a hundred of them
at once — that module is about concurrency, this one is about truth.
"""

from __future__ import annotations

from ..providers.chat import ChatProvider
from ._prompt import PROMPT, RETRY
from .oracle import review

__all__ = ["author_one", "MAX_TOKENS"]

MAX_TOKENS = 400
_SKELETON_LINES = 15     # what a degraded card keeps


def author_one(provider: ChatProvider, model: str, relpath: str, skeleton: str, *,
                others: set[str]) -> tuple[str, bool]:
    """One card, oracle-gated, one retry. (text, degraded).

    The skeleton is both the prompt's content and the oracle's grounding set —
    one source, so the gate can only reject a name the model was never shown.
    """
    prompt = PROMPT.format(relpath=relpath, skeleton=skeleton)
    for _attempt in range(2):
        try:
            text = provider.chat_text(model, prompt, max_tokens=MAX_TOKENS).strip()
        except Exception:            # noqa: BLE001 — degrade, never abort the pass
            break
        problems = review(text, relpath=relpath, skeleton=skeleton,
                          other_paths=others)
        if not problems:
            return text, False
        prompt = RETRY.format(relpath=relpath, skeleton=skeleton,
                              problems="; ".join(problems))
    return "\n".join(skeleton.split("\n")[:_SKELETON_LINES]), True
