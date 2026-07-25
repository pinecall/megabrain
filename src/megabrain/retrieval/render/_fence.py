"""A fenced code block, tagged with the language the path implies."""

from __future__ import annotations

from ._lang import lang_of

__all__ = ["fenced"]


def fenced(text: str, relpath: str) -> list[str]:
    return [f"```{lang_of(relpath)}", text.rstrip("\n"), "```"]
