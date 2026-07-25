"""The atlas: a model-written mental map of the repository.

Pieces with a hard line between them:

- `author` (LLM, index time) — writes one card per file from its skeleton.
- `oracle` (no LLM) — accepts or rejects each card against the symbol table.
- `brief` + `render` (no LLM, query time) — cosine over the cards, relations
  rendered live from the graph, interfaces from the symbol table.

The line is the point: prose is authored once, behind a gate, and every query
after that is deterministic. The query path must never import `providers.chat`.
"""

from __future__ import annotations

from .author import CARD_SCHEMA, write_cards
from .brief import brief_repo
from .oracle import review
from .render import render_brief

__all__ = ["CARD_SCHEMA", "write_cards", "brief_repo", "render_brief", "review"]
