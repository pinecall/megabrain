"""SURFACE CLOSURE LOOP — megabrain_search rebuilt for AGENTS.

An agent calling megabrain_search needs the COMPLETE edit surface in one
answer. The open-loop pipeline (score → tiers → one-shot expander → judge)
verifies nothing: when a facet of the task is missing, the OUTER agent
discovers it at 30-60s per turn with host greps. This module moves that
discovery INSIDE the engine, where a turn costs ~1s of the fast lane:

    base retrieve ─► PLAN (1 call): decompose the request into the facets
                     an implementer must touch (declare / consume / display /
                     serialize / collide / configure ...)
                 ─► PROBE fan-out (one call PER FACET, parallel): each names
                     DIRECTIVES — identifiers to grep, symbols to resolve,
                     focused sub-queries — never spans
                 ─► deterministic RESOLUTION of every directive:
                     grep over chunk texts · dense re-search · symbol def
                     sites. Chunks enter the pool as PURE ADDITIONS.
                 ─► VERIFY fan-out (parallel critics): "could a maintainer
                     implement this reading ONLY these spans?" Unresolved
                     holes loop once more, then stop.

Up to `call_cap` internal LLM calls (default 30), parallel, fast-lane only
(~1s wall-clock per round, ~$0.01 total on flash-lite).

Locked-rule compliance:
- the LLM NEVER picks spans — it only NAMES what to look for; every chunk
  that enters the pool was resolved by a deterministic lane (same
  anti-hallucination stance as the expander and ask's citation splice).
- pure additions: nothing is displaced or re-ranked; bundle completeness
  can only rise (the recall-floor doctrine).
- fail-open EVERYWHERE: no key, timeout, garbage JSON, call-cap hit → the
  deterministic result stands untouched.
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

MAX_FACETS = 8          # probe fan-out width per round
VERIFIERS = 3           # parallel critics per verify step
MAX_ROUNDS = 2          # probe→verify cycles (round 2 only if holes remain)
CALL_CAP = 30           # hard budget of internal LLM calls per search
CARD_LINES = 90         # surface card shown to the LLMs (spans, no bodies)
GREP_DF_CAP = 20        # a directive term matching more impl chunks is noise
PER_DIRECTIVE_CAP = 4   # chunks a single directive may add
ADD_CAP = 24            # total chunks the whole loop may add

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

_PLAN = """An engineer must FULFILL this request against a codebase:

{query}

Current retrieval surface (file:lines · symbols):
{card}

Decompose the WORK into up to {k} facets an implementer must touch or
consult — e.g. where the mechanism is declared/configured, where it is
consumed/resolved, how it is displayed/serialized, error/collision
handling, the adjacent config. Name facets AS THEY APPLY TO THIS request,
not generically. Return ONLY a JSON array of short facet strings."""

_PROBE = """Request an engineer must fulfill:

{query}

The facet YOU own: {facet}

Surface retrieved so far (file:lines · symbols):
{card}

Name what to LOOK UP so your facet's code is fully present in the surface.
Return ONLY JSON:
{{"grep": ["exact_identifier", ...], "symbols": ["DefinitionName", ...],
  "queries": ["focused sub-query", ...]}}
Prefer identifiers you can see referenced in the surface's symbols but
whose definition/usage spans are absent. Use [] for empty slots. Never
invent file paths."""

_VERIFY = """Request an engineer must fulfill:

{query}

Retrieved surface (file:lines · symbols):
{card}

Could a maintainer implement the request END-TO-END reading ONLY these
spans? Think about every place the change must touch. Return ONLY JSON:
{{"closed": true}}  — or —
{{"closed": false, "grep": ["identifier", ...], "symbols": ["Name", ...],
  "queries": ["what is still missing", ...]}}"""


def _json_of(reply: str):
    """First JSON value in a reply; raises on none (caller fails open)."""
    m = re.search(r"[\[{].*[\]}]", reply, re.S)
    if not m:
        raise ValueError(f"no JSON in reply: {reply[:120]!r}")
    return json.loads(m.group(0))


def _card(chunks: list[dict]) -> str:
    """Spans + symbols only — what the internal LLMs are allowed to see.
    No bodies: probers must NAME lookups, not quote code."""
    lines = []
    for c in chunks[:CARD_LINES]:
        name = (c.get("name") or c.get("kind") or "?")
        lines.append(f'{c["file"]}:{c["start_line"]}-{c["end_line"]} · {name}')
    return "\n".join(lines)


class _Budget:
    def __init__(self, cap: int):
        self.cap, self.used = cap, 0

    def take(self, n: int = 1) -> bool:
        if self.used + n > self.cap:
            return False
        self.used += n
        return True


def _resolve(st, metas, fused, directives: dict, have: set) -> list[tuple[int, str]]:
    """Deterministically resolve directives to chunk indexes (metas space).
    Returns [(index, why)] — capped, deduped, implementation chunks only
    (tests/docs have their own sections and closures)."""
    from .scoring import _is_demo_path, _is_test_path
    impl = [i for i, m in enumerate(metas)
            if not _is_test_path(m.file) and not _is_demo_path(m.file)]
    out: list[tuple[int, str]] = []
    seen: set = set(have)

    def add(i: int, why: str) -> None:
        mid = metas[i].id
        if mid not in seen and len(out) < ADD_CAP:
            seen.add(mid)
            out.append((i, why))

    for t in dict.fromkeys(directives.get("grep") or []):
        if not isinstance(t, str) or not (3 <= len(t) <= 80):
            continue
        matched = [i for i in impl if t in (metas[i].text or "")]
        if 0 < len(matched) <= GREP_DF_CAP:
            for i in sorted(matched, key=lambda i: -float(fused[i]))[:PER_DIRECTIVE_CAP]:
                add(i, f"grep:{t}")

    for s in dict.fromkeys(directives.get("symbols") or []):
        if not isinstance(s, str) or not s:
            continue
        base = s.rsplit(".", 1)[-1]
        try:
            hits = st.store.find_symbols(base)
        except Exception:
            hits = []
        for h in hits[:2]:
            line = h.get("line") or 0
            for i in impl:
                m = metas[i]
                if m.file == h.get("file") and m.start_line <= line <= m.end_line:
                    add(i, f"symbol:{base}")
                    break

    qs = [q for q in (directives.get("queries") or [])
          if isinstance(q, str) and q.strip()][:3]
    if qs:
        from .scoring import score_chunks
        for q in qs:
            try:
                m2, f2 = score_chunks(st, q, None, exclude_docs=True)
            except Exception:
                continue
            id_at = {mm.id: j for j, mm in enumerate(metas)}
            import numpy as np
            for j in np.argsort(-f2)[:PER_DIRECTIVE_CAP]:
                i = id_at.get(m2[int(j)].id)
                if i is not None and i in set(impl):
                    add(i, "query")
    return out


def close_surface(st, query: str, res: dict, model: str | None = None) -> dict | None:
    """Run the closure loop over a prune result IN PLACE. Appends probed
    chunks to res["chunks"] tagged with `facet`, records res["closure"].
    Returns the closure record, or None on full fail-open."""
    t0 = time.time()
    try:
        from .rerank import judge_lane
        chat, m, _ = judge_lane(model)
        from .scoring import score_chunks
        metas, fused = score_chunks(st, query, None, exclude_docs=True)
        budget = _Budget(CALL_CAP)
        have = {c["id"] for c in res["chunks"]}
        added: list[dict] = []
        facets: list[str] = []
        rounds = 0
        closed = False

        def call(prompt: str):
            return chat(m, prompt, 300, timeout=25)

        # PLAN — once
        if budget.take():
            try:
                got = _json_of(call(_PLAN.format(
                    query=query, card=_card(res["chunks"]), k=MAX_FACETS)))
                facets = [str(f)[:80] for f in got][:MAX_FACETS] \
                    if isinstance(got, list) else []
            except Exception:
                log.debug("closure plan failed open", exc_info=True)

        pending: list[str] = list(facets)
        while rounds < MAX_ROUNDS and not closed:
            rounds += 1
            # PROBE fan-out — one call per pending facet, parallel
            probes: list[dict] = []
            todo = [f for f in pending if budget.take()]
            if todo:
                def _probe(f: str) -> dict:
                    try:
                        d = _json_of(call(_PROBE.format(
                            query=query, facet=f, card=_card(res["chunks"]))))
                        return d if isinstance(d, dict) else {}
                    except Exception:
                        return {}
                with ThreadPoolExecutor(max_workers=len(todo)) as ex:
                    probes = list(ex.map(_probe, todo))
            for d in probes:
                for i, why in _resolve(st, metas, fused, d, have):
                    c = {**metas[i].to_dict(), "score": float(fused[i]),
                         "facet": why}
                    have.add(c["id"])
                    added.append(c)
                    res["chunks"].append(c)

            # VERIFY fan-out — parallel critics; majority closed → stop
            n_v = min(VERIFIERS, budget.cap - budget.used)
            if n_v <= 0:
                break
            budget.take(n_v)

            def _verify(_k: int) -> dict:
                try:
                    d = _json_of(call(_VERIFY.format(
                        query=query, card=_card(res["chunks"]))))
                    return d if isinstance(d, dict) else {"closed": True}
                except Exception:
                    return {"closed": True}     # a dead critic never loops us
            with ThreadPoolExecutor(max_workers=n_v) as ex:
                verdicts = list(ex.map(_verify, range(n_v)))
            n_closed = sum(1 for v in verdicts if v.get("closed"))
            closed = n_closed * 2 >= len(verdicts)
            if not closed:
                # holes become the next round's directives (merged, no plan)
                merged: dict = {"grep": [], "symbols": [], "queries": []}
                for v in verdicts:
                    for k in merged:
                        merged[k] += [x for x in (v.get(k) or [])
                                      if isinstance(x, str)]
                for i, why in _resolve(st, metas, fused, merged, have):
                    c = {**metas[i].to_dict(), "score": float(fused[i]),
                         "facet": why}
                    have.add(c["id"])
                    added.append(c)
                    res["chunks"].append(c)
                pending = []            # round 2 re-verifies, no re-plan

        res["kept"] = len(res["chunks"])
        rec = {"facets": facets, "rounds": rounds, "closed": closed,
               "added": len(added), "calls": budget.used,
               "ms": int((time.time() - t0) * 1000)}
        res["closure"] = rec
        return rec
    except Exception:
        log.debug("closure failed open", exc_info=True)
        return None
