"""Phase 2 — one embedding call for the whole pass.

Every chunk and every file skeleton goes out in a single list and is sliced
back apart afterwards. Embedding per file means two round trips per changed
file (a file's few chunks never fill a batch, and its skeleton travels as a
request of one), which turns a cold index on a large repository into minutes of
sequential waiting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from .._arrays import Vector
from ..chunkers import embed_text
from ._plan import Planned

__all__ = ["Embeddable", "Vectors", "embed_all"]

Progress = Callable[[dict[str, object]], None]


class Embeddable(Protocol):
    """The slice of the embedder this phase needs — a seam for testing.

    `model` is declared as a property, not a bare attribute: a plain annotation
    in a Protocol demands a SETTABLE one, which would reject any implementation
    that exposes it read-only.
    """

    @property
    def model(self) -> str: ...

    def embed(self, texts: Sequence[str], *,
              on_batch: Callable[[int, int], None] | None = None) -> list[Vector]: ...


@dataclass(frozen=True, slots=True)
class Vectors:
    """Vectors for one file, already sliced out of the shared batch."""

    chunks: list[Vector]
    skeleton: Vector | None


def embed_all(pending: Sequence[Planned], embedder: Embeddable,
              on_progress: Progress | None = None) -> list[Vectors]:
    """Embed everything at once, then hand each file back its own rows.

    The slicing is positional, so the order texts were added in IS the contract
    between this function and its caller — which is why both loops below walk
    `pending` the same way rather than rebuilding the order from the results.
    """
    texts: list[str] = []
    spans: list[tuple[int, int, bool]] = []
    for item in pending:
        start = len(texts)
        texts.extend(embed_text(c.breadcrumb, c.text, c.part) for c in item.result.chunks)
        has_skeleton = bool(item.result.skeleton)
        if has_skeleton:
            texts.append(item.result.skeleton)
        spans.append((start, len(item.result.chunks), has_skeleton))

    vectors = embedder.embed(texts, on_batch=_ticker(on_progress)) if texts else []
    if len(vectors) != len(texts):
        # Positional slicing makes the count part of the contract. A reply one
        # row short does not raise on its own: the slices simply walk off the
        # end, so a file's skeleton becomes the next file's chunk and the
        # shortfall is only visible as an index that ranks strangely.
        raise ValueError(f"embedder returned {len(vectors)} vectors "
                         f"for {len(texts)} texts")
    return [Vectors(chunks=vectors[start:start + count],
                    skeleton=vectors[start + count] if skeleton else None)
            for start, count, skeleton in spans]


def _ticker(on_progress: Progress | None) -> Callable[[int, int], None] | None:
    if on_progress is None:
        return None
    return lambda done, total: on_progress({"type": "embed", "done": done, "total": total})
