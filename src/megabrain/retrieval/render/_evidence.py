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
    lines = _judge_line(bundle)
    band = bundle.get("evidence", "strong")
    if band == "weak":
        lines.append("> ⚠ **thin evidence** — the closest match is weak "
                     f'(top cosine {bundle.get("top_cosine", 0):.2f}). '
                     "Verify before relying on it.\n")
    if band == "none":
        lines.append("> ⚠ **nothing in this repo clearly answers this** "
                     f'(top cosine {bundle.get("top_cosine", 0):.2f}). '
                     "The files below merely share vocabulary with the question.\n")
    return lines


def _judge_line(bundle: Bundle) -> list[str]:
    """The judge's verdict, when it spoke and rejected everything.

    None and kept-0 are different answers: silence on None (the lane never
    ran), one plain sentence on kept-0 — the reader is about to scan a RELATED
    list that a model already read in full and dismissed, and that is worth
    exactly one line before they spend the time.
    """
    verdict = bundle.get("judge")
    if verdict is None or verdict["kept"] > 0 or not bundle["tier2"]:
        return []
    return [f'> ⚠ **the judge kept none of the {verdict["of"]} RELATED files** '
            "— they merely share vocabulary with the task. CORE stands on its "
            "own.\n"]


