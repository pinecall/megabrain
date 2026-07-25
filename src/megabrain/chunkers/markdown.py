"""Markdown, by heading.

A document's structure IS its headings, so they are the units: a section is
what somebody means when they cite a doc, and the nesting gives the engine the
same cut points a class gives it in code.

Fenced code is skipped while scanning. A `#` at the start of a line inside a
shell block is a comment, and treating it as a heading cuts the block in half —
the reader gets the second half of an example with no command above it.
"""

from __future__ import annotations

import re

from .model import Symbol
from .units import Parsed, Unit

__all__ = ["parse"]

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
FRONTMATTER = "---"
MAX_TITLE = 140


def parse(relpath: str, source: str) -> Parsed:
    lines = source.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    found = _headings(lines)
    symbols = tuple(_symbol(relpath, entry, len(lines)) for entry in found)
    return Parsed(units=tuple(_nest(found, len(lines))), symbols=symbols,
                  skeleton=_skeleton(relpath, found), ok=True)


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line, level, title) for every heading outside a code fence."""
    found: list[tuple[int, int, str]] = []
    fenced = False
    for number, line in enumerate(lines, start=1):
        if number == 1 and line.strip() == FRONTMATTER:
            fenced = True            # YAML front matter, closed by its own ---
            continue
        if line.strip() == FRONTMATTER and fenced and number > 1:
            fenced = False
            continue
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if match := HEADING.match(line):
            found.append((number, len(match.group(1)), match.group(2)[:MAX_TITLE]))
    return found


def _nest(found: list[tuple[int, int, str]], total: int) -> list[Unit]:
    """Top-level sections, each carrying its subsections as cut points.

    A section runs to the next heading of the SAME OR SHALLOWER level — which is
    what makes `## Install` include its own `### macOS` rather than stopping at
    it.
    """
    return _sections(found, 0, len(found), total)


def _sections(found: list[tuple[int, int, str]], start: int, stop: int,
              end_line: int) -> list[Unit]:
    units: list[Unit] = []
    index = start
    while index < stop:
        line, level, title = found[index]
        inner = index + 1
        while inner < stop and found[inner][1] > level:
            inner += 1
        section_end = (found[inner][0] - 1) if inner < stop else end_line
        units.append(Unit(start_line=line, end_line=max(line, section_end),
                          kind="section", name=title,
                          children=tuple(_sections(found, index + 1, inner,
                                                   section_end))))
        index = inner
    return units


def _symbol(relpath: str, entry: tuple[int, int, str], total: int) -> Symbol:
    line, level, title = entry
    return Symbol(file=relpath, name=title, kind=f"h{level}", line=line,
                  end_line=total, signature=f"{'#' * level} {title}")


def _skeleton(relpath: str, found: list[tuple[int, int, str]]) -> str:
    """The table of contents, which is what a document declares."""
    lines = [f"# {relpath}"]
    lines += [f"{'    ' * (level - 1)}{title}" for _line, level, title in found]
    return "\n".join(lines)
