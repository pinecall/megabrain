"""Reading and writing somebody else's config file.

The rule the whole module exists to keep: megabrain owns exactly ONE key. The
file belongs to the person who wrote it — their other MCP servers, their
unrelated top-level settings and, in the TOML case, their comments all have to
come out the other side untouched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .platforms import SERVER_NAME, Platform

__all__ = ["is_registered", "write"]

Entry = dict[str, Any] | None      # None means "remove megabrain"


def is_registered(path: Path, platform: Platform) -> bool:
    """Unreadable counts as unregistered: this answers a display question, and
    the write path is where a broken file gets reported properly."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if platform.fmt == "toml":
        return bool(re.search(rf"^\[{re.escape(platform.key)}\.{SERVER_NAME}\]",
                              text, re.M))
    try:
        loaded: Any = json.loads(text or "{}")
    except json.JSONDecodeError:
        return False
    return SERVER_NAME in (loaded.get(platform.key) or {})


def write(path: Path, platform: Platform, entry: Entry) -> None:
    """Add, replace or drop the megabrain entry, in the host's own format."""
    if platform.fmt == "toml":
        _write_toml(path, platform.key, entry)
    else:
        _write_json(path, platform.key, entry)


def _write_json(path: Path, key: str, entry: Entry) -> None:
    """Merge, never rewrite. The entry is REPLACED rather than updated in
    place: a stale PYTHONPATH from an old checkout is precisely what
    re-running this is supposed to cure, and merging would preserve it."""
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
        except json.JSONDecodeError as err:
            raise ValueError(f"{path} is not valid JSON — fix it first ({err})") from err
    servers: dict[str, Any] = data.setdefault(key, {})
    if entry is None:
        servers.pop(SERVER_NAME, None)
    else:
        servers[SERVER_NAME] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


_TOML_BLOCK = r"^\[{key}\.{name}\]\n(?:(?!^\[).*\n?)*"


def _write_toml(path: Path, key: str, entry: Entry) -> None:
    """A targeted section replace/append.

    The stdlib has no TOML writer and megabrain takes no dependencies, so the
    section is edited as text — which is also why it must match only up to the
    next `[`, and never round-trip the whole document.
    """
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    block = re.compile(_TOML_BLOCK.format(key=re.escape(key), name=SERVER_NAME), re.M)
    new = block.sub("", text) if entry is None else _replaced(text, block, key, entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")


def _replaced(text: str, block: re.Pattern[str], key: str,
              entry: dict[str, Any]) -> str:
    args = ", ".join(json.dumps(a) for a in entry["args"])
    section = (f"[{key}.{SERVER_NAME}]\n"
               f"command = {json.dumps(entry['command'])}\n"
               f"args = [{args}]\n")
    if block.search(text):
        return block.sub(section, text)
    return text.rstrip("\n") + "\n\n" + section if text.strip() else section
