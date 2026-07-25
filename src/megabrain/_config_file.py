"""Reading a JSON file a person edits by hand.

Every function here answers the same question — "is this field the shape it
should be, and if not, what now" — and the answer is always the same: take what
is valid, ignore what is not, and never let one wrong field take the file down.
Half a valid config is the normal state of a file somebody is editing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence, cast

__all__ = ["read_object", "string_tuple", "string_map", "lines_of"]


def read_object(path: Path) -> tuple[dict[str, Any], bool]:
    """The config, and whether a file was there but unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}, False
    try:
        loaded: object = json.loads(text)
    except ValueError:
        return {}, True
    return (cast("dict[str, Any]", loaded), False) if isinstance(loaded, dict) else ({}, True)


def string_tuple(value: object) -> tuple[str, ...]:
    """A list of strings, or nothing. A string is NOT accepted as a
    one-element list: `"ignore": "dist"` is a mistake worth noticing, and
    guessing at it teaches the wrong shape."""
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in cast("Sequence[object]", value) if str(item).strip())


def string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item)
            for key, item in cast("dict[str, object]", value).items() if item}


def lines_of(path: Path) -> tuple[str, ...]:
    """A legacy one-per-line file: `#` comments and blanks dropped.

    Still read because repositories in the wild have these, and dropping them
    would silently start indexing directories somebody deliberately excluded.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return tuple(stripped for line in text.splitlines()
                 if (stripped := line.split("#", 1)[0].strip()))
