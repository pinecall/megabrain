"""The verb `ask`: retrieve deterministically, then explain what was found.

The two halves are deliberately unequal. Retrieval is the product — no model,
milliseconds, and it decides WHAT the answer is built from. The model only
explains it, and cannot add code. So the bundle is emitted as an event before
any model runs: a caller that stops reading there still has the real answer.

The flow cache sits between them. A near-exact question whose code has not
changed is answered from it with no model at all; a related one is attached as
context and narrated fresh. Both decisions are cosine and file hashes — hard
rule #1 survives, because nothing on the read path calls a model.
"""

from __future__ import annotations

from pathlib import Path

from .._provider_errors import MissingCredential
from .._types import Content
from ..contracts import Bundle, FlowHit
from ..converse.backend import narrator_for
from ..events import Emit, emit_nothing
from ..search import search
from ..storage.locate import resolve_root
from ._flows import matched_flows, remember_answer, served
from .narrator import narrate

__all__ = ["ask"]


def ask(start: Path | str, question: str, *, path_filter: str | None = None,
        content: Content | None = "code", cache: bool = True,
        emit: Emit = emit_nothing) -> str:
    """A narrated walkthrough of the code that answers `question`.

    `content` defaults to CODE, unlike search: a code walkthrough diluted with
    prose explains the documentation instead of the mechanism.

    `cache` turns the flow cache off for one call — for measuring what the
    engine does cold, which is impossible if the second run answers from the
    first.
    """
    root = resolve_root(start)
    bundle = search(start, question, path_filter=path_filter, content=content)
    emit({"type": "retrieval", "repo": bundle["repo"], "ms": bundle["ms"],
          "core": [entry["file"] for entry in bundle["tier1"]],
          "related": len(bundle["tier2"])})

    flows = matched_flows(root, question) if cache else []
    if flows and (hit := served(root, question, flows, emit)) is not None:
        return hit["text"]

    provider = narrator_for(root)
    if provider is None:
        # Named, not a generic failure: retrieval already worked, and the only
        # thing missing is a credential the message can point at.
        raise MissingCredential.named("MEGABRAIN_CHAT_API_KEY")
    # `root` is what lets the narrator OPEN files: retrieval is where the answer
    # starts, and the span that matters can sit fifty lines below the chunk that
    # matched. Without it the walkthrough is one buffered call over the chunks.
    answer = narrate(provider, question, _with_flows(bundle, flows),
                     root=root, emit=emit)
    if cache:
        remember_answer(root, question, answer, bundle, emit)
    return answer


def _with_flows(bundle: Bundle, flows: list[FlowHit]) -> Bundle:
    """The matched flows, carried on the bundle for the narrator to read.

    Attached, never merged: a flow is context ABOUT the code, and mixing it
    into the candidate list would let cached prose compete with real chunks for
    citation — which is exactly how a walkthrough ends up citing a summary.
    """
    return {**bundle, "flows": flows}
