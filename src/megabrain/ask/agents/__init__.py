"""Fan-out: one sub-narrator per subsystem, pooled.

For a question that spans more of a repository than one prompt can hold. The
subagents share the retrieval core and never share a context."""

from __future__ import annotations
