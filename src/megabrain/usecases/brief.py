"""The verb `brief`: the mental model for a question.

The cheap half of the atlas: no LLM, no network beyond one query embedding,
an answer in milliseconds. `search` returns the code; `brief` returns what a
reader needs BEFORE the code — what each file is, how they connect, and where
the bodies live.
"""

from __future__ import annotations

from pathlib import Path

from ..atlas import brief_repo
from ..contracts import Brief
from ..storage.locate import resolve_root

__all__ = ["brief"]


def brief(start: Path | str, question: str, *, limit: int = 10,
          rerank: bool = False, embedder: object = None) -> Brief:
    """Answer `question` for whichever repository `start` belongs to.

    `rerank` runs the SAME judge lane search offers, on the same bundle,
    before the brief selects its files — one policy, two surfaces, and the
    same fail-open contract: no provider, the deterministic order stands.
    `embedder` is the same injection seam as in `search`.
    """
    root = resolve_root(start)
    return brief_repo(root, question, limit=limit, embedder=embedder,
                      judge=_judge_for(root) if rerank else None)


def _judge_for(root: Path):  # -> Callable[[Bundle], Bundle] | None
    """The judge closure, with the model THIS repo chose — shared verbatim
    with `search`'s policy so the two surfaces cannot drift."""
    from ..enrich.rerank import judge_provider
    from ..enrich.rerank import rerank as judged
    from ..project import load_project

    provider = judge_provider(load_project(root).rerank_model)
    if provider is None:
        return None
    return lambda bundle: judged(bundle, provider)
