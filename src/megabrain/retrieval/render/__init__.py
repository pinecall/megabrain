"""Rendering a bundle for a reader. One renderer, every surface."""

from __future__ import annotations

from ._lang import lang_of
from .markdown import render

__all__ = ["render", "lang_of"]
