"""Optional lanes that use a model to improve a bundle.

The contract is one line: `Bundle -> Bundle`. Every enricher is opt-in and
FAIL-OPEN — on any failure it returns its input unchanged, so a provider
outage costs ordering and never the answer.

Layer 4. Nothing under `retrieval/` may import this, and a test enforces it:
the deterministic engine is the product, and an LLM in its path was measured
four ways and cost completeness every time.
"""

from __future__ import annotations

from .rerank import rerank

__all__ = ["rerank"]
