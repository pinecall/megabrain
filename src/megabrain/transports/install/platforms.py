"""The table: which assistants exist, and where each one keeps its MCP config.

megabrain speaks MCP, and MCP is portable — the SAME stdio server works in all
six. Only the config file differs (path, format, key), so the differences live
here as data and every other module in this package is format-agnostic.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Literal

__all__ = ["SERVER_NAME", "MODULE", "Platform", "PLATFORMS", "entry"]

SERVER_NAME = "megabrain"
MODULE = "megabrain.transports.mcp"

Format = Literal["json", "toml"]


@dataclass(frozen=True, slots=True)
class Platform:
    """`path` and `dir_hint` are relative to $HOME.

    `dir_hint` is what proves the product is installed even before it has ever
    written an MCP config — a fresh Codex has the directory and no file.
    """

    label: str
    path: str
    fmt: Format
    key: str
    dir_hint: str


PLATFORMS: dict[str, Platform] = {
    "claude": Platform("Claude Code", ".claude.json", "json", "mcpServers",
                       ".claude"),
    "codex": Platform("Codex", ".codex/config.toml", "toml", "mcp_servers",
                      ".codex"),
    "antigravity": Platform("Antigravity", ".gemini/antigravity/mcp_config.json",
                            "json", "mcpServers", ".gemini/antigravity"),
    "cursor": Platform("Cursor", ".cursor/mcp.json", "json", "mcpServers",
                       ".cursor"),
    "windsurf": Platform("Windsurf", ".codeium/windsurf/mcp_config.json", "json",
                         "mcpServers", ".codeium/windsurf"),
    # NOT ".gemini" — that directory also exists for Antigravity, which nests
    # under it; keying off the settings FILE avoids claiming Gemini CLI is
    # installed when only Antigravity is.
    "gemini": Platform("Gemini CLI", ".gemini/settings.json", "json",
                       "mcpServers", ".gemini/settings.json"),
}


def entry() -> dict[str, Any]:
    """The server entry, pinned to THIS interpreter.

    `sys.executable`, never the bare name: a host launches the command with its
    own PATH, and the python it finds is regularly not the one megabrain is
    installed in. Pinning also means re-running the install repairs a config
    that drifted to an old checkout, instead of adding a second broken entry.
    """
    return {"command": sys.executable, "args": ["-m", MODULE]}
