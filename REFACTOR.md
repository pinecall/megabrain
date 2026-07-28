# REFACTOR — the gap between "works" and 10/10

Findings from a full read of the source tree (`src/megabrain/`, `studio/src/`,
`tests/`, 2026-07-28). Everything below **passed the gates on the day it was
written down** — that is exactly why it was: a green suite does not argue with
a design error. Ordered by severity; each item names the files, the failure it
enables, and the fix.

**Status 2026-07-28: items 1–9 are FIXED**, each landed test-first (RED
before the change) with the full gate green after. What each fix actually
became is recorded inline — the shipped shape differs from the sketched one in
a few places, and the difference is worth keeping. Items 10–13 remain open.

Rules referenced: **[LAY]** dependency arrows point down only · **[OCP]**
extend, don't modify · **[R4]** reuse before rewriting · **[SEC]** security /
abuse surface · **[SCALE]** breaks at repository or deployment scale.

---

## P0 — design errors (wrong even though they work) — ALL FIXED

### 1. ✅ `grep/` imports `ask/`'s privates — a layering inversion [LAY]

`grep/` earned its own top-level package precisely so "no model in the lanes"
is an importable fact — and its verb still reached into the package it
escaped, six imports deep, three of them `_`-private (`grep.py`,
`referenced.py`, `rows.py` → `ask.converse.loop`, `ask.prompt._candidates`,
`ask.prompt._chunkblocks`, `ask.ask._narrator`, `ask.citing._quote.lines_of`,
`ask.checks.surface`).

**Fixed** by promoting the shared pieces to homes that import neither verb:

- `lines_of` → **`storage/lines.py`** (it is a Store reader, nothing more);
- the conversation loop, tool schemas, toolless fallback and gap-filling →
  a top-level **`converse/`** package (was `ask/converse/`; the ask-specific
  `_flowctx` stayed behind in `ask/`);
- `candidates_of`/`chunk_blocks` → `converse/candidates.py` /
  `converse/chunkblocks.py` (the measured bodies-vs-map balance both verbs
  must share);
- narrator resolution → **`converse/backend.narrator_for`** (`ask.ask` and
  `grep --why` both call it);
- `import_surface` → **`grep/surface.py`** (its only consumer);
- `ask/events.py` → top-level **`events.py`** (zero-dependency vocabulary).

Two new architecture tests pin it: `test_grep_never_imports_ask` (no module
under `grep/` may import `megabrain.ask`, verb included) and
`test_converse_is_neutral_ground` (`converse/` imports no verb). The existing
lanes test now fences `megabrain.converse` instead of `ask.converse`.

### 2. ✅ The rate limiter cannot see through a reverse proxy [SEC]

`transports/http/_handler.py` keyed the rate limit on `client_address[0]` and
`ui` had no `--trust-proxy` (v2 had the flag; the public demo's runbook uses
it). Behind nginx every caller is the proxy's IP. **Fixed:**
`Policy.trust_proxy` + `Guard.caller_of(remote, forwarded)` — the first
`X-Forwarded-For` hop, only when the flag is set (trusting the header on a
directly-exposed box lets any caller mint identities, the opposite bug) —
wired through the handler and a `--trust-proxy` flag on `ui`. Pinned in
`tests/unit/transports/test_security.py` and the CLI test.

### 3. ✅ `Guard._hits` grows forever [SEC] [SCALE]

The per-caller deques were pruned by time but the dict keys never were — one
entry per distinct caller IP for the life of the process, growable at will
once #2 landed. **Fixed** with `_forget_departed`: an amortised sweep (at most
once per `WINDOW`, under the same lock) dropping every caller whose whole
window expired. The test grows 1000 callers and asserts one live caller
reclaims them all.

---

## P1 — logic and scale risks — ALL FIXED

### 4. ✅ The judge's timeout is per-batch, not per-lane [R4]

`enrich/_batches.py` promised *"ONE hung batch bounds the whole lane"* but
`future.result(timeout=wall)` restarted the wall per future (~k×wall for k
staggered slow batches), and `max_workers=len(batches)` was unbounded.
**Fixed:** `gathered(futures, wall, clock)` computes ONE deadline and gives
each wait only what the earlier ones left (injectable clock, so the tests are
instant and exact); the pool is capped at `MAX_JUDGES = 4`. The lane still
fails open — a spent deadline raises and `rerank` catches it as before.

### 5. ✅ `~/.megabrain/registry.json` writes race [SCALE]

`remember()` was read-modify-write with no lock on a file co-owned with v2 —
two concurrent `index` runs could silently drop an entry that no re-index
brings back for the *other* engine's user. **Fixed:**
`usecases/_registry.update_entries(target, mutate)` holds an exclusive OS
lock (`usecases/_lockfile.py` — `flock` / `msvcrt.locking` on a `.lock` file
*beside* the registry, because the write path atomically replaces the target
and a lock on a replaced inode guards nothing) across the whole
read-modify-write. Pinned by a 24-writer thread race test.

### 6. ✅ The graph keeps an O(n²) matrix and rebuilds per request [SCALE]

`semantic_lane` returned the full cosine matrix (400 MB at 10 k files, per
`graph_map` call) and the HTTP route rebuilt the whole graph every request.
**Fixed both halves:** the lane now computes cosines in 512-row blocks and
extracts the surprise candidates (pairs ≥ `SURPRISE_MIN`, which moved in
beside the other cosine floors) while each block exists — `RepoGraph.sims`/
`sim_files` are gone, replaced by `twins`; `surprises_of` checks the two legs
that need the rest of the graph (no edge, different communities). And
`graph/warm.py` caches the built `RepoGraph` keyed by the index file's stat
(a content fingerprint needs the graph to compute — exactly the work the
cache skips), used by every served view (`views`, `node`, `routes/route`).

### 7. ✅ The embedding cache never shrinks [SCALE]

**Fixed:** `EmbedCache.size()` / `.prune(older_than_days)` (the sweep lives
in `providers/embeddings/janitor.py`, mtime-based), surfaced as **`megabrain
cache`** (report) and **`megabrain cache prune --older-than N`** (sweep,
default 90 days) — a dedicated command rather than a line inside `scan`,
because the cache is machine-global and `scan` is about one repository.
Never automatic: deleting cache during an index is how you pay twice.

### 8. ✅ The intent and coverage lanes are English-only [SCALE]

**Fixed:** the keyword tables moved to **`search/wording.py`** as data
(question openers, change-verb stems, wanting phrases, test nouns) covering
**Spanish, Portuguese, French and German**; `flows/covers.py` gained the four
languages' scaffolding stop-words and a unicode-aware word regex (the ASCII
one split `búsqueda` into `b`+`squeda`, poisoning the coverage ratio for
every accented language). English keeps its measured exact lists. Other
languages still get the conservative default, now documented in
`docs/REFERENCE.md` ("Query-language coverage"). Pinned by
`tests/unit/search/test_intent_languages.py`.

### 9. ✅ `enrich` echoes its own naming split [R4]

**Fixed** by renaming so every "the wording IS the behaviour" module greps as
a prompt: `enrich/_prompt.py` → `_judge_prompt.py`, `enrich/_terms.py` →
`_expand_prompt.py`, `grep/words.py` → `grep/_prompt.py`.

---

## P2 — product debt (the road already named) — OPEN

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

### 12. ✅ `forge/` — phase 16 (ported 2026-07-28)

Landed as `forge/` (detect · oracle · coverage · report · probes · measure ·
changed · granularity · ab_gate · opportunities · diagnose · specialize) plus
`indexing/trust.py` (the sha-gated trust store + repo-local loading, wired
into `index_repo`) and `indexing/chunking.py` (`chunker_for`, which honours a
strategy's optional `budget` — what makes the lit-2000 baseline three lines
instead of v2's reach into a private chunker). v3's contract made the forge
SAFER than v2's: the model writes a PARSER (`parse -> Parsed`) and the
engine's `Chunker` owns the partition, while the oracle still rejects units
past EOF, raising parsers and line-inaccurate symbols. CLI: `megabrain forge
[--ext] [--dry-run] [--attempts] [--model]`. 24 offline tests; golden gate
byte-identical.

### 13. Version truth

`_version.py` currently overstates what PyPI serves (published latest:
0.18.6). Reconcile to `0.19.0` before tagging — the guard job in
`release.yml` will otherwise refuse the tag, which is the guard working.

### ⚠️ Observed while gating the fixes above (2026-07-28)

The golden gate on this machine reads **R@1 0.91 · bundle_full 0.77 · p50
61 ms** — *identical before and after every change in this file* (verified
against a clean HEAD worktree, same six misses), so it is not a regression:
the fixes are byte-identical on retrieval. But 0.77 is not the documented
1.00, which means the local `~/pinecall` corpus has drifted from
`golden.json` (cut 2026-06-12) or its index state has. **Re-cut or re-verify
the corpus before any phase-17 work** — a gate that starts at 0.77 cannot
detect a completeness regression.

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
- [x] **Fix P0 1–3** — the layering inversion and the two public-box holes
      are the difference between "audited" and "audited except". *(Done, see
      above.)*
- [ ] **Issue mode** (11; forge — 12 — is done): close the v2 parity list so
      "rewrite complete" is simply true.
- [ ] **Scale honesty** (partly done: 6 and 7 are fixed; still owed is a
      `LIMITS.md` section stating the measured envelope — chunks per repo
      before p50 moves, cache growth per model — with the numbers, the same
      way every other constant in this codebase is documented).
- [ ] **The rename** (10) plus a versioned MCP-tool deprecation policy, so
      agent integrations can trust the surface across minors.
- [ ] **Community surface:** CONTRIBUTING already points at "add a language"
      — make it real with a cookiecutter test (`tests/unit/chunkers/
      test_languages.py` is already parametrised; a new language is a
      `LangSpec` + one `Case`). Add issue templates that ask for the census
      (`megabrain scan`) output — the diagnosis is usually in it.

**10/10 does not exist. This list is the argument for 9.5.**
