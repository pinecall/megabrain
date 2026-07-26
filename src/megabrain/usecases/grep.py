"""The verb `grep`: where to look, and nothing else.

The third of three deliverables over ONE retrieval core, and the division is
what each is measured to be good at:

  grep    you are about to EDIT — files, symbols, real line ranges, one line of
          why each. No code, because the host's editor opens the file anyway and
          the retired `megabrain_code` proved that citing it is billed twice.
  ask     you want to UNDERSTAND, or to copy a mechanism out of another
          repository — the flow narrated with the real code spliced in.
  search  you want the MAP, or the docs — chunks straight from the index, no
          model. Never the input for an edit: it ranks what exists, so a missing
          call or flag is exactly what it cannot show you.

Not cached, unlike `ask`. A walkthrough stays true until the code moves; a list
of edit sites is consumed once by the change that invalidates it.
"""

from __future__ import annotations

from pathlib import Path

from .._provider_errors import MissingCredential
from ..ask._candidates import candidates_of
from ..ask._chunkblocks import chunk_blocks
from ..ask._converse import answered
from ..ask._grepwords import GREP_PROMPT
from ..ask._sites import sites_from
from ..ask.events import Emit, emit_nothing
from ..storage import Store
from ..storage.locate import resolve_root
from .ask import _narrator
from .search import search

__all__ = ["grep"]


def grep(start: Path | str, task: str, *, path_filter: str | None = None,
         emit: Emit = emit_nothing) -> str:
    """The files and symbols `task` has to touch, with their real line ranges."""
    root = resolve_root(start)
    bundle = search(start, task, path_filter=path_filter, content="code")
    emit({"type": "retrieval", "repo": bundle["repo"], "ms": bundle["ms"],
          "core": [entry["file"] for entry in bundle["tier1"]],
          "related": len(bundle["tier2"])})
    provider = _narrator(root)
    if provider is None:
        raise MissingCredential.named("MEGABRAIN_CHAT_API_KEY")
    # The SAME context the walkthrough gets: the best bodies with their code,
    # the rest as a map. Measured — handed only a list of names, the model chose
    # a constant over the function beside it and a sibling tool over the one the
    # task described. Choosing which symbol matters needs the code; only the
    # ANSWER has to be small.
    blocks = chunk_blocks(candidates_of({**bundle, "flows": []}))
    prompt = GREP_PROMPT.replace("{task}", task).replace("{map}", blocks)
    answer = answered(provider, prompt, root, emit=emit)
    with Store(root) as store:
        sites = sites_from(store, answer.text, task=task)
    # The model's own words survive ONLY when it produced no rows — that is how
    # "nothing here is relevant" reaches the caller instead of an empty answer.
    rendered = sites or answer.text.strip()
    emit({"type": "delta", "text": rendered})
    return rendered
