"""ask — a narrated walkthrough whose every line of code is real.

Layer 4: this package uses an LLM and NOTHING under retrieval may import it.
The division is the product. Retrieval is deterministic and answers in
milliseconds; ask explains what retrieval found, and is allowed to be slow and
probabilistic because it can never invent code — it cites, and the engine
splices the bytes.
"""

from __future__ import annotations

from .citing.citations import Citation, parse_citations
from .citing.splice import splice

__all__ = ["splice", "parse_citations", "Citation"]
