"""A chunk as it comes BACK from the index — the query-time row view.

Deliberately not a TypedDict, and that distinction is the whole point of this
file. `contracts/` describes what crosses a BOUNDARY: dicts, because they get
serialised to JSON and read by the MCP client, the HTTP API and the studio.
`ChunkMeta` never leaves the process: it is the hot-path record that scoring
touches once per chunk per query, where attribute access on a slotted
dataclass beats dict lookups and a typo is a crash instead of a KeyError at
render time.

The `vec` is absent on purpose. Vectors live in one numpy matrix whose row `i`
belongs to `metas[i]`; carrying a copy per record would double the memory and
invite the two to drift.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ChunkMeta"]


@dataclass(frozen=True, slots=True)
class ChunkMeta:
    """One indexed chunk, minus its vector. Frozen: retrieval reads, never
    edits — a lane that wants to change a score changes the score ARRAY."""

    id: int
    file: str
    kind: str
    name: str | None
    part: str | None
    start_line: int
    end_line: int
    text: str
    breadcrumb: str

    @property
    def lines(self) -> tuple[int, int]:
        return self.start_line, self.end_line

    def overlaps(self, start: int, end: int) -> bool:
        """Whether this chunk intersects a line span — how a traceback pin or a
        grep hit finds the chunk that contains it."""
        return not (self.end_line < start or self.start_line > end)
