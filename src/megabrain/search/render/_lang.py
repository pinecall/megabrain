"""File extension -> the language name a markdown fence expects.

Its own module because it is a lookup table that grows with every content type
the engine learns, and a table growing inside a renderer is how a renderer
turns into a place people are afraid to touch.
"""

from __future__ import annotations

__all__ = ["lang_of"]

_BY_EXTENSION = {
    "py": "python", "pyi": "python",
    "ts": "typescript", "tsx": "tsx", "js": "javascript", "jsx": "jsx",
    "mjs": "javascript", "cjs": "javascript",
    "rb": "ruby", "go": "go", "rs": "rust", "php": "php",
    "md": "markdown", "markdown": "markdown", "mdx": "markdown",
}


def lang_of(relpath: str) -> str:
    """The fence tag, or "" — an unknown extension gets a plain fence rather
    than a guess that turns a highlighter into a liar."""
    return _BY_EXTENSION.get(relpath.rsplit(".", 1)[-1].lower(), "")
