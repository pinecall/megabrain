"""DEEP RETRIEVER — the internal agent behind megabrain_search for agents.

The outer coding agent must receive EVERYTHING in ONE search render: every
edit site, the constructor/config surface, the TESTS whose conventions its
new tests must copy, the doc sections, the changelog head. Field evidence
(click#3652 duel): the render held the key mechanism, but the tests section
is pointer-only — the outer agent burned turns grepping `multiple=True` and
reading test bodies at 30-60s per OUTER turn. This module runs that hunt
INSIDE the engine at ~1-3s per INTERNAL turn.

Unlike the closure loop (a critic that only NAMES identifiers), the deep
retriever is a real agent: a multi-turn loop where the model sees the
package manifest, calls INTERNAL tools (grep / search / add-spec — all
resolved deterministically by grepx / prune_search / readx), and declares
`done` when the package suffices. The model chooses WHICH specs enter; the
CODE is always rendered verbatim from disk (readx) — same anti-hallucination
stance as ask's citation splice: selection is LLM, content never is.

Fail-open everywhere: no lane, timeout, garbage JSON, budget hit → the
deterministic result stands. Model: the fast judge lane by default;
MEGABRAIN_DEEP_MODEL pins a stronger retriever (e.g. a Sonnet-class model
via OpenRouter) when quality beats latency.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

log = logging.getLogger(__name__)

MAX_TURNS = 5
MAX_SPECS = 14          # specs the retriever may add to the package
TOOL_FEED_CHARS = 3200  # per-turn tool-result feedback shown to the model
MANIFEST_LINES = 70
WALL_BUDGET_S = 45      # hard wall-clock cap for the whole loop

_PROMPT = """You are megabrain's internal RETRIEVER. An implementation agent
will receive ONLY the package you assemble — it CANNOT search again. Gather
everything needed to implement the request: every edit site, the
constructor/declaration surface, display/serialization sites, the TESTS
whose conventions the new tests must follow (their bodies, not just names),
the doc sections to update, the changelog head.

Request:
{query}

Package so far (each line is already rendered verbatim to the implementer):
{manifest}

Tool results from your previous turn:
{feedback}

Reply ONLY one JSON object:
{{"actions": [
   {{"tool": "grep", "pattern": "exact_string"}},
   {{"tool": "search", "query": "focused sub-query"}},
   {{"tool": "add", "specs": ["path#Symbol", "path:START-END"]}}
 ],
 "done": false}}
`add` specs must come from tool results or the manifest — never invent
paths. Set "done": true when the package suffices (actions may be empty).
You have {turns} turn(s) left and may add {slots} more spec(s)."""


def _grep_feed(root, pattern: str) -> str:
    """Role-grouped grep, compacted for the retriever's context."""
    from .. import app
    try:
        res = app.grep(root, pattern)
    except Exception:
        return f"grep {pattern!r}: failed"
    lines = [f"grep {pattern!r}: {res.get('matches', 0)} match(es)"]
    for sec in ("defines", "reads", "config", "tests", "docs"):
        for m in (res.get(sec) or [])[:4]:
            lines.append(f'  {sec}: {m["file"]}:{m["line"]} · '
                         f'{(m.get("symbol") or "")} · {m["text"][:70]}')
    return "\n".join(lines[:18])


def _search_feed(st, query: str) -> str:
    """Compact deterministic re-search: spans + symbols, no bodies."""
    from .bundle import prune_search
    try:
        res = prune_search(st, query, with_text=False, exclude_docs=True)
    except Exception:
        return f"search {query!r}: failed"
    lines = [f"search {query!r}:"]
    for c in res["chunks"][:10]:
        lines.append(f'  {c["file"]}:{c["start_line"]}-{c["end_line"]} · '
                     f'{(c.get("name") or c.get("kind") or "?")}')
    return "\n".join(lines)


def _validate_specs(root, specs: list) -> list[str]:
    """Keep only specs that resolve on disk (readx does the real parsing)."""
    from .readx import read_specs
    good: list[str] = []
    for s in specs:
        if not isinstance(s, str) or not s.strip():
            continue
        try:
            res = read_specs(root, [s.strip()])
        except Exception:
            continue
        if any("error" not in t for t in res["targets"]):
            good.append(s.strip())
    return good


def _manifest(res: dict, specs: list[str]) -> str:
    lines = []
    for c in res["chunks"][:MANIFEST_LINES]:
        lines.append(f'{c["file"]}:{c["start_line"]}-{c["end_line"]} · '
                     f'{(c.get("name") or c.get("kind") or "?")}')
    for s in specs:
        lines.append(f"{s}  (added by you)")
    return "\n".join(lines)


def deep_retrieve(st, root, query: str, res: dict,
                  model: str | None = None) -> dict | None:
    """Run the internal retriever loop. Attaches res["deep"] with the specs
    to render as the package's `retrieved context` section. Fail-open."""
    t0 = time.time()
    try:
        from .rerank import judge_lane
        chat, m, _ = judge_lane(model)
        m = os.environ.get("MEGABRAIN_DEEP_MODEL") or m
        specs: list[str] = []
        feedback = "(none — first turn)"
        turns = 0
        done = False
        while turns < MAX_TURNS and not done and len(specs) < MAX_SPECS \
                and time.time() - t0 < WALL_BUDGET_S:
            turns += 1
            prompt = _PROMPT.format(query=query,
                                    manifest=_manifest(res, specs),
                                    feedback=feedback[:TOOL_FEED_CHARS],
                                    turns=MAX_TURNS - turns + 1,
                                    slots=MAX_SPECS - len(specs))
            reply = chat(m, prompt, 500, timeout=30)
            mjson = re.search(r"\{.*\}", reply, re.S)
            if not mjson:
                break
            got = json.loads(mjson.group(0))
            done = bool(got.get("done"))
            feeds: list[str] = []
            for a in (got.get("actions") or [])[:6]:
                if not isinstance(a, dict):
                    continue
                tool = a.get("tool")
                if tool == "grep" and isinstance(a.get("pattern"), str):
                    feeds.append(_grep_feed(root, a["pattern"]))
                elif tool == "search" and isinstance(a.get("query"), str):
                    feeds.append(_search_feed(st, a["query"]))
                elif tool == "add":
                    ok = _validate_specs(root, a.get("specs") or [])
                    room = MAX_SPECS - len(specs)
                    specs += [s for s in ok if s not in specs][:room]
                    feeds.append(f"added: {', '.join(ok) or '(none valid)'}")
            feedback = "\n\n".join(feeds) or "(no actions)"
        if not specs:
            return None
        # resolve the bodies HERE (the renderer stays I/O-free), skipping any
        # spec fully covered by a signal chunk that already renders its body —
        # the package never pays a span twice
        from .readx import read_specs
        covered = [(c["file"], c["start_line"], c["end_line"])
                   for c in res["chunks"] if c.get("text")]
        blocks = []
        for t in read_specs(root, specs)["targets"]:
            if "error" in t:
                continue
            if any(f == t["file"] and s <= t["start"] and t["end"] <= e
                   for f, s, e in covered):
                continue
            blocks.append(t)
        rec = {"specs": specs, "turns": turns, "done": done, "blocks": blocks,
               "ms": int((time.time() - t0) * 1000), "model": m}
        res["deep"] = rec
        return rec
    except Exception:
        log.debug("deep retriever failed open", exc_info=True)
        return None
