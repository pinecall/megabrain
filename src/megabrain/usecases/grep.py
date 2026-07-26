"""The verb `grep`: where to look, and NO MODEL unless you ask for one.

The third of three deliverables over one retrieval core:

  grep    you are about to EDIT — files, symbols, real line ranges. No code,
          because the host's editor opens the file anyway and the retired
          `megabrain_code` proved that citing it is billed twice.
  ask     you want to UNDERSTAND, or to copy a mechanism out of another
          repository — the flow narrated with the real code spliced in.
  search  you want the MAP, or the docs — chunks straight from the index. Never
          the input for an edit: it ranks what EXISTS, so a missing call is
          exactly what it cannot show you.

The default runs NO model, and that was measured after being built the wrong way
round. On click's `show_envvar_value` task the deterministic lanes alone returned
10 of the 11 rows in **0.05 s**; adding the model took **1.3 s** — 26× — and
bought one extra row plus a note on each. A tool that replaces `grep` cannot
charge a model call and a second of latency by default, and hard rule #1 says
retrieval never calls a model.

`why=True` buys that extra row back. It is the one a literal search can never
reach: on that task, `Option.get_help_record` never contains the string
`show_envvar` — it reads `extra["envvars"]` — so no search for the task's own
words finds it, and the model's judgement is the only thing that does.
"""

from __future__ import annotations

from pathlib import Path

from ..ask._candidates import candidates_of
from ..ask._chunkblocks import chunk_blocks
from ..ask._converse import answered
from ..ask._grepwords import GREP_PROMPT
from ..ask._sites import sites_from
from ..ask.events import Emit, emit_nothing
from ..storage import Store
from ..storage.locate import resolve_root
from .search import search

__all__ = ["grep"]


def grep(start: Path | str, task: str, *, path_filter: str | None = None,
         why: bool = False, emit: Emit = emit_nothing) -> str:
    """The files and symbols `task` has to touch, with their real line ranges."""
    root = resolve_root(start)
    bundle = search(start, task, path_filter=path_filter, content="code")
    emit({"type": "retrieval", "repo": bundle["repo"], "ms": bundle["ms"],
          "core": [entry["file"] for entry in bundle["tier1"]],
          "related": len(bundle["tier2"])})
    judged = _judged(root, bundle, task, emit) if why else ""
    with Store(root) as store:
        sites = sites_from(store, judged, task=task)
        if not sites and not why:
            # MEASURED across ten repositories, and it is why this fallback is
            # not optional: the literal lane fires only when the TASK spells an
            # identifier the repo already has. Told to "describe the outcome, not
            # the file" — which this tool's own description asks for — eight of
            # ten tasks named nothing existing and returned ZERO rows. Fast and
            # empty is worse than slow and right, so an empty result pays for the
            # model rather than handing back nothing.
            emit({"type": "unmatched", "reason": "no identifier the index knows"})
            judged = _judged(root, bundle, task, emit)
            sites = sites_from(store, judged, task=task)
    rendered = sites or judged.strip() or f"nothing in this index matches: {task}"
    emit({"type": "delta", "text": rendered})
    return rendered


def _judged(root: Path, bundle: dict, task: str, emit: Emit) -> str:
    """One model pass naming the sites and why — the opt-in half.

    Given the SAME context the walkthrough gets: the best bodies with their code,
    the rest as a map. Measured — handed only a list of symbol NAMES, the model
    chose a constant over the function beside it and a sibling tool over the one
    the task described. Judging which symbol matters needs the code; only the
    ANSWER has to be small.

    Fails OPEN: with no credential the deterministic rows are still the answer,
    so a missing key degrades the render instead of the command.
    """
    from .ask import _narrator

    provider = _narrator(root)
    if provider is None:
        emit({"type": "unjudged", "reason": "no chat credential"})
        return ""
    blocks = chunk_blocks(candidates_of({**bundle, "flows": []}))
    prompt = GREP_PROMPT.replace("{task}", task).replace("{map}", blocks)
    return answered(provider, prompt, root, emit=emit).text
