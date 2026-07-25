"""`megabrain install` — register the MCP server with your coding assistants.

megabrain speaks MCP, and MCP is portable: the SAME stdio server works in
Claude Code, Codex, Antigravity, Cursor, Windsurf and Gemini CLI. Only the
config file differs, so the differences are a table (`platforms`), the file
formats are one module (`configs`), and the decision of what to touch is
another (`apply`). Nothing here knows anything about retrieval.

Two properties worth keeping: megabrain only ever writes its own key, and the
entry is pinned to the interpreter it is installed in, so re-running repairs a
config that drifted rather than adding a second broken one.
"""

from __future__ import annotations

from .apply import apply, detect
from .platforms import PLATFORMS, Platform
from .render import render, render_detected

__all__ = ["detect", "apply", "render", "render_detected", "PLATFORMS", "Platform"]
