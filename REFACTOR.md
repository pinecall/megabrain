# REFACTOR — the gap between "works" and 10/10

Findings from a full read of the source tree (`src/megabrain/`, `studio/src/`,
`tests/`, 2026-07-28). Everything below **passes the gates today** — that is
exactly why it is written down: a green suite does not argue with a design
error. Ordered by severity; each item names the files, the failure it enables,
and the fix. Unless marked, a fix lands with the golden gate byte-identical.

Rules referenced: **[LAY]** dependency arrows point down only · **[OCP]**
extend, don't modify · **[R4]** reuse before rewriting · **[SEC]** security /
abuse surface · **[SCALE]** breaks at repository or deployment scale.

---

## P0 — design errors (wrong even though they work)

### 1. `grep/` imports `ask/`'s privates — a layering inversion [LAY]

`grep/` earned its own top-level package precisely so "no model in the lanes"
is an importable fact. Its verb still reaches into **the package it escaped**,
three of the targets private by name:

```
grep/grep.py:31        from ..ask.converse.loop import answered
grep/grep.py:33        from ..ask.prompt._candidates import candidates_of
grep/grep.py:34        from ..ask.prompt._chunkblocks import chunk_blocks
grep/grep.py:84        from ..ask.ask import _narrator          ← a PRIVATE function
grep/referenced.py:22  from ..ask.citing._quote import lines_of
grep/rows.py:16        from ..ask.checks.surface import import_surface
```

Two L4 siblings with an arrow between them means a change to `ask/`'s
internals can break `grep` with no test naming the coupling — and `_narrator`
imported across a package boundary is a privacy the underscore no longer
means anything by. **Fix:** promote the five shared pieces to a neutral home
(`lines_of` belongs beside `storage` readers; `import_surface`,
`candidates_of`, `chunk_blocks`, the narrator resolution into a shared
`ask`-independent module — or an L4 `_shared/`), then add the missing
architecture test: `grep/` may import `providers.chat` only in its `--why`
verb module, and `ask/` not at all.

### 2. The rate limiter cannot see through a reverse proxy [SEC]

`transports/http/_handler.py:62` keys the rate limit on
`self.client_address[0]`, and the `ui` command exposes no `--trust-proxy`
(`transports/cli/commands/ui.py` — v2 had the flag; the public demo's runbook
uses it). Behind nginx **every caller is the proxy's IP**: one abusive client
exhausts the sliding window for everyone, and the operator cannot tell abuse
from popularity. **Fix:** a `Policy.trust_proxy` flag; when set, `Guard`
reads the first `X-Forwarded-For` hop. Off by default — trusting the header
on a directly-exposed box lets any caller mint identities, which is the
opposite bug.

### 3. `Guard._hits` grows forever [SEC] [SCALE]

`transports/http/security.py`: the per-caller deques are pruned by time, but
**the dict keys never are**. A public box accumulates one entry per distinct
caller IP for the life of the process — an unbounded map an attacker can grow
deliberately with spoofed forwarded addresses once #2 lands. **Fix:** drop a
caller's entry when its deque empties during pruning (two lines, same lock).

---

## P1 — logic and scale risks

### 4. The judge's timeout is per-batch, not per-lane [R4]

`enrich/_batches.py` claims *"ONE hung batch bounds the whole lane"*, but
`future.result(timeout=wall)` is evaluated **sequentially per future** — the
wall restarts for each one, so k staggered slow batches bound the lane at
~k×wall, not wall. Also `ThreadPoolExecutor(max_workers=len(batches))` is
unbounded in the number of batches. Both are small today (tier-2 is ~20
entries → 3 batches) and wrong by construction. **Fix:** one deadline
(`monotonic() + wall`), each `result(timeout=deadline - now)`; cap workers.

### 5. `~/.megabrain/registry.json` writes race [SCALE]

`usecases/repos.py` `remember()` is read-modify-write with **no lock** on a
file explicitly co-owned with the v2 engine. Two concurrent `index` runs (or
v2 and v3 at once — the exact scenario the module documents) can interleave
and silently drop an entry; the suite tests merge semantics, not concurrency.
**Fix:** the same atomic pattern the embed cache already uses — write to a
temp file and `replace()` — plus a retry-on-change loop or an `fcntl`/msvcrt
lock. Losing a registry entry is data no re-index brings back for the *other*
engine's user.

### 6. The graph keeps an O(n²) matrix and rebuilds per request [SCALE]

`graph/semantic.py` returns the **full cosine matrix** (kept for surprises):
10 000 files with skeletons is 100 M float32 = **400 MB**, transient per
`graph_map` call — and `transports/http/routes/graph.py` rebuilds the whole
graph on every request (only the *labels* are cached, under the graph
fingerprint). The studio's Graph tab makes this a click-frequency cost.
**Fix:** (a) compute surprises inside `semantic_lane` and discard the matrix
(top-k already exists; surprises need one extra masked argpartition, not the
matrix); (b) cache the built `RepoGraph` in the server process keyed by the
same fingerprint the labels already use.

### 7. The embedding cache never shrinks [SCALE]

`providers/embeddings/cache.py` is content-addressed and correct, and has
**no eviction**: every model ever pointed at (`~/.megabrain/embeddings`)
keeps its full corpus of vectors forever. Switching models twice on a large
repo triples the footprint silently. **Fix:** an `mtime`-based sweep behind
`megabrain cache prune` (never automatic — deleting cache during an index is
how you pay twice), and a size line in `megabrain scan`/`ui` so the growth is
at least visible.

### 8. The intent and coverage lanes are English-only [SCALE]

Three deterministic classifiers are keyword regexes over English:
`search/intent.py` (`wants_tests`, `is_task`), `flows/covers.py` (the STOP
list). For a Spanish or Chinese query every one of them silently returns the
conservative default — the test penalty never stands down, tasks are answered
as questions, the flow cache never serves verbatim. The *failure direction*
is safe (features turn off, nothing lies), but for a tool whose own author
queries it in Spanish, three lanes being dead is a product gap nobody is
told about. **Fix:** at minimum, document it in `docs/REFERENCE.md`; better,
add the top-5 languages' keyword sets to the same tables — they are data,
not code, which is the shape these modules already chose.

### 9. `enrich` echoes its own naming split [R4]

`enrich/_terms.py` builds the expander prompt, `enrich/_prompt.py` the
judge's, `grep/words.py` the grep one — three "the wording IS the behaviour"
modules with three different naming conventions (`_terms`, `_prompt`,
`words`). Cosmetic until someone greps for "the prompt" and finds one of
three. **Fix:** one convention (`_prompt.py` per package) in the next touch
of each file; not worth its own commit.

---

## P2 — product debt (the road already named)

### 10. `grep` → `map` [naming]

The deliverable is a **map of the task's edit surface**; the verb name
collides with the tool it replaces and undersells the difference (the README
now says so). **Fix when taken:** rename the MCP tool to `megabrain_map`
keeping `megabrain_grep` registered as a deprecated alias for two minors;
CLI `map` with `grep` as an argparse alias (the `ui`/`studio` pattern,
`transports/cli/commands/ui.py`, is the template); `GrepParams` →
`MapParams` with a re-export.

### 11. Issue mode — the last behavioural-parity gap

v2's long-query lane (BM25 over entity-IDs + traceback/identifier grounding
pins for bug-report-shaped queries) is not ported. It reweights, so it needs
no new shape: one more `Lane` beside `TestPenalty` in
`search/scoring/lanes.py`, self-gated on query length. It does not fire on
the golden set — port it **with its own golden cases**, or it will regress
invisibly forever.

### 12. `forge/` — phase 16

The self-authored chunkers (LLM writes a `ChunkStrategy`, accepted only if
`validate_partition` passes on every matching file, sha-trust-gated). The
oracle and the trust store already exist; the port is the last phase before
algorithm work is allowed.

### 13. Version truth

`_version.py` currently overstates what PyPI serves (published latest:
0.18.6). Reconcile to `0.19.0` before tagging — the guard job in
`release.yml` will otherwise refuse the tag, which is the guard working.

---

## The road to 10/10 as an open-source project

What the engine already has is rarer than what it lacks: enforced invariants,
measured defaults, an offline suite, typed contracts, Trusted-Publishing
releases. The remaining distance is **external legibility** — a stranger being
able to verify the claims without trusting the author:

- [ ] **A public benchmark.** The golden corpus is private; `evals/harness/`
      is committed but unrunnable by outsiders. Publish a small public corpus
      (5–8 permissively-licensed repos + queries, the `benchmarks/` pin
      pattern already does this for the grep A/B) and wire `bundle_full` into
      CI on it. Then run one recognised external set (SWE-bench-retrieval or
      CodeSearchNet) once and publish the numbers, including the losses.
- [ ] **Fix P0 1–3** — the layering inversion and the two public-box holes
      are the difference between "audited" and "audited except".
- [ ] **Issue mode + forge** (11, 12): close the v2 parity list so
      "rewrite complete" is simply true.
- [ ] **Scale honesty** (6, 7): a `LIMITS.md` section stating the measured
      envelope — chunks per repo before p50 moves, files before the graph
      matrix hurts, cache growth per model — with the numbers, the same way
      every other constant in this codebase is documented.
- [ ] **The rename** (10) plus a versioned MCP-tool deprecation policy, so
      agent integrations can trust the surface across minors.
- [ ] **Community surface:** CONTRIBUTING already points at "add a language"
      — make it real with a cookiecutter test (`tests/unit/chunkers/
      test_languages.py` is already parametrised; a new language is a
      `LangSpec` + one `Case`). Add issue templates that ask for the census
      (`megabrain scan`) output — the diagnosis is usually in it.

**10/10 does not exist. This list is the argument for 9.5.**
