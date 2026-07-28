"""Reading and writing a registry file this engine does not own alone.

Three shapes are accepted because three have existed: the other engine's dict
keyed by path, a plain list of paths, and a list of objects. Tolerance here is
the whole point — a reader that understands only its own shape reports an empty
machine, and a writer that emits only its own destroys the other's list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, cast

from ._lockfile import held

__all__ = ["read_entries", "write_entries", "update_entries"]


def read_entries(target: Path) -> dict[str, dict[str, Any]]:
    """The registry, whatever shape it is in, as path -> entry.

    Three shapes are accepted because three have existed: the other engine's
    dict, a plain list of paths, and a list of objects. Anything unreadable
    reads as empty — this file is a convenience, and refusing to start because
    a JSON file on the side is corrupt would make it a dependency.
    """
    try:
        loaded: object = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(loaded, dict):
        return {str(key): _fields(value)
                for key, value in cast("dict[str, object]", loaded).items()}
    if isinstance(loaded, list):
        return dict(_from_item(item) for item in cast("list[object]", loaded))
    return {}


def _from_item(item: object) -> tuple[str, dict[str, Any]]:
    """A list entry, which historically was either a path or an object."""
    fields = _fields(item)
    if fields:
        return str(fields.get("path", "")), fields
    return str(item), {"path": str(item)}


def _fields(value: object) -> dict[str, Any]:
    return dict(cast("dict[str, Any]", value)) if isinstance(value, dict) else {}


def write_entries(target: Path, entries: dict[str, dict[str, Any]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Temp file and rename: a crash mid-write would otherwise leave truncated
    # JSON, and the next read would silently see no repositories at all.
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(entries, indent=1, sort_keys=True), encoding="utf-8")
    temp.replace(target)


def update_entries(target: Path,
                   mutate: Callable[[dict[str, dict[str, Any]]], None]) -> None:
    """Read, mutate, write — under an OS lock, so two writers cannot interleave.

    The atomic rename above protects a READER from a torn file; it does nothing
    for two writers, whose read-modify-write windows overlap and silently drop
    whichever entry landed first. Two `index` runs — or this engine and the one
    it replaces — hit that for real on a file that is nobody's to regenerate.
    """
    with held(target):
        entries = read_entries(target)
        mutate(entries)
        write_entries(target, entries)
