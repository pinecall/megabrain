"""The honesty line above a rendered bundle.

Its own module because it is the one piece of the renderer with a POLICY in it:
when the engine's evidence band says "weak" or "none", the text has to change
what the reader does with everything below it — and that wording deserves to be
findable, testable and quotable on its own.
"""

from __future__ import annotations

from ...contracts import Bundle

__all__ = ["evidence_banner"]


def evidence_banner(bundle: Bundle) -> list[str]:
    """The honesty line, when there is something to be honest about.

    Silent on "strong" — a banner on every answer is a banner on none. The
    wording on "none" names what the reader should DO with the list that
    follows: treat it as nearest vocabulary, not as an answer.
    """
    band = bundle.get("evidence", "strong")
    if band == "weak":
        return ["> ⚠ **thin evidence** — the closest match is weak "
                f'(top cosine {bundle.get("top_cosine", 0):.2f}). '
                "Verify before relying on it.\n"]
    if band == "none":
        return ["> ⚠ **nothing in this repo clearly answers this** "
                f'(top cosine {bundle.get("top_cosine", 0):.2f}). '
                "The files below merely share vocabulary with the question.\n"]
    return []


