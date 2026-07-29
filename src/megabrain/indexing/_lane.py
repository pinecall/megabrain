"""One language\'s import graph, as a pair of functions.

Build the repo-wide context, then read a file against it. Both halves travel
together, so the context a lane is handed is always the one it built — no
isinstance narrowing needed, unlike the built-in strategies where the registry
could hand over a sibling\'s context.

Its own module so that adding a graph to a language is a ROW in the language
table (`_languages.py`) rather than a subclass: v2 grew Ruby, Go and PHP
graphs by subclassing three times, and the rewrite dropped all three.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

__all__ = ["EdgeLane"]


@dataclass(frozen=True, slots=True)
class EdgeLane:
    context: Callable[[dict[str, str]], object]
    edges: Callable[[str, str, object], list[tuple[str, str]]]
