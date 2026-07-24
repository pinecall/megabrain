# megabrain v3 — the rewrite plan

**This file is the contract. Follow it to the letter. When it conflicts with an
instinct, the file wins.**

Executor: **Fable 5** (`claude-fable-5`).
Source of truth for current behavior: `~/megabrain-v2` (v1.0.0, 58 files, 13 878 LOC).
Architecture framework: the `art-of-python` skill (`~/.claude/skills/art-of-python/`).
Reference implementation to imitate: `~/experiments/anthropic-sdk-python` (indexed).

---

## STATUS — read this before touching anything

**Phases 0–7 are done, gated, and committed.** Phases 8–17 (§6) have not
started. This section is the truth as of commit `68cc934`; the plan below it
is unchanged from when it was written and still describes what's left.

### Verify the state yourself before trusting this section

```bash
cd ~/megabrain-v3
git log --oneline -1                                   # 68cc934
git log --oneline | wc -l                               # 209
git tag | wc -l                                          # 34
./scripts/lint                                            # ruff + mypy + pyright + architecture
python3 -m pytest tests -q                                 # 293 collected
```

### What exists

```
src/megabrain/
├── _types.py _arrays.py _errors.py _version.py __init__.py     L0
├── contracts/            chunk.py bundle.py prune.py            L1 — TypedDicts only
├── storage/               store.py schema.py model.py            L2
│                          _blobs.py _chunks.py _files.py _symbols.py _graph.py
├── providers/             http.py _retry.py _urllib.py _wire.py   L2 (embeddings)
│                          _config.py cache.py embeddings.py
├── chunkers/               units.py model.py cast.py python.py     L3
│                          _spans.py _merge.py _split.py _balance.py
│                          _breadcrumb.py _signature.py _pysymbols.py
└── retrieval/              params.py paths.py state.py search.py   L3 — NO LLM, enforced
   ├── scoring/             lane.py lanes.py context.py pipeline.py
   ├── bundle/              assemble.py _rank.py _related.py floors.py
   └── _render.py

evals/harness/gate.py    the golden-set runner, versioned (the private corpus is not)
tests/                   293 tests: unit/ (chunkers, indexing, providers, storage),
                         contracts/ (shape validation against captured payloads),
                         architecture/ (the hard rules, executable), golden/
```

`providers/chat`, `enrich/`, `knowledge/`, `ask/`, `usecases/`, `transports/`
and `studio/` do not exist yet — that's phases 8–16.

### Gate status right now

| Gate | Result |
|---|---|
| ruff | clean |
| mypy strict | clean, 63 files |
| pyright strict | clean, 0 errors |
| pytest | **290 passed, 2 failed, 1 skipped** (293 collected) |
| golden (`evals/harness/gate.py` against `~/pinecall/sdk-server`) | **R@1 0.91 · bundle_full 1.00 · p50 ~11ms — matches v2 exactly, same 2 misses (q01, q03)** |
| `retrieval/` importing `providers.chat` or `enrich` | zero occurrences (checked by AST walk, not just grep) |

The golden gate is not wired into `pytest` by default — it needs
`MEGABRAIN_GOLDEN` and `MEGABRAIN_GOLDEN_REPO` pointing at a real corpus (see
`tests/golden/test_gate.py`), which is why `pytest` alone shows it skipped.
Without those two env vars set, **you cannot verify retrieval parity** — set
them before touching anything under `retrieval/` or `providers/embeddings.py`.

### Known debt — start here

Two of `tests/architecture/test_invariants.py`'s own line-budget checks
currently **fail**. This is self-inflicted (the fixes above were shipped under
time pressure to close phase 7) and is exactly the kind of thing this round
should fix:

1. **`src/megabrain/providers/_wire.py` — 117 lines (budget 100).**
   Grew past budget across two bug fixes (denormal detection, then
   out-of-order row correction). Needs a real split, not a squeeze — the width
   detection (`_decode`/`_has_magnitude`) and the row-ordering fix
   (`_ordered`) are two distinct concerns that both currently live in one file
   with `decode_batch`.
2. **`src/megabrain/retrieval/bundle/assemble.py` — 105 lines (budget 100).**
   `search_with_state` plus its four private helpers. `_anchors` is the
   obvious extraction candidate — it's the newest addition and the one that
   pushed the file over.

Fix both the way every other split in this codebase was done: read the file,
find the seam that was already implicit, extract to a new module, re-run
`./scripts/lint` and the golden gate, confirm parity numbers are unchanged.
**Do not just delete comments or compress lines to fit the budget** — the
budget is diagnostic, not the goal; a forced-thin file with the same logic and
no explanation is worse than the violation.

### Two real bugs found and fixed during phase 7 (context for review)

Both were caught by comparing behavior against the live embeddings endpoint
and against v2's actual request/response handling — not by unit tests with
fake data, which had the bugs baked into their own fixtures and couldn't see
them. Worth knowing before reviewing `providers/`:

1. **Wire format detection.** The endpoint can return base64-encoded float32
   *or* int8, and misreading one as the other doesn't crash — it produces
   either a dimension mismatch (loud) or finite-but-denormal floats around
   `1e-42` that underflow to zero on normalization (silent, and the vector
   then scores against nothing). `_decode`/`_has_magnitude` in
   `providers/_wire.py` check three things before trusting a float32 read:
   byte-count divisibility by 4, `isfinite`, and magnitude above `1e-20`.
2. **Row ordering.** The embeddings endpoint may answer batched requests
   out of order and says so via an `index` field per row. The code did not
   sort by it. This is the single worst class of bug the module can have —
   nothing raises, every text gets *a* vector, just not necessarily its own —
   and it was found only by manually diffing this code's request/response
   handling against v2's line by line, not by any test. Fixed in `_ordered()`
   in `_wire.py`; falls back to arrival order if `index` is absent (some
   OpenAI-compatible endpoints omit it).

**Lesson for this round:** don't trust a green test suite alone when a module
talks to something external. Re-derive the wire contract from a real request/
response pair (or from the older implementation's actual behavior, not its
docstring) before assuming the code matches it.

### Not yet ported (known, deliberate, not a regression)

Phase 7's commit message already flagged these; repeating here so this round
doesn't rediscover them as mysteries:

- **Issue mode** — the long-query lane (BM25 sparse entity-ID matching +
  traceback/identifier grounding pins for bug-report-shaped queries). v2 had
  it as a fourth scoring lane; v3's `scoring/lanes.py` has three
  (`DenseFileFusion`, `TestPenalty`, `LexicalBoost`). It does not fire on the
  golden set, which is why parity holds without it — but it needs to exist
  before v3 can claim full behavioral parity with v2, not just golden-set parity.
- **The cached-answer (flow) lane.** `Bundle.flows` is wired in the contract
  and always returns `[]` in `assemble.py`. `storage/flows.py`'s equivalent
  (the SQLite `flows` table, its cache-attach/serve split) has not been
  ported at all.
- **`related_entry`'s `via_flow` field** exists in the contract
  (`contracts/bundle.py`) precisely because the flow lane is coming — it's not
  dead code, it's a contract written ahead of its producer.

### What this round should do, roughly in order

1. **Fix the two budget violations above.** Small, mechanical, low-risk —
   good warm-up before touching anything with retrieval-quality risk.
2. **Audit `providers/` and `retrieval/` for the same CLASS of bug** the two
   fixes above represent: silent-wrong-answer failure modes in code that
   talks to something external or does array arithmetic. Look especially at
   `chunkers/_split.py`/`_balance.py` (weight-based splitting, fixed once
   already against a real corpus — see phase 5's commit) and
   `retrieval/bundle/floors.py` (the two recall floors — read the "why" in
   their docstrings and check the code still does what they say).
3. **Re-run the golden gate after any change touching `retrieval/`,
   `chunkers/`, or `providers/embeddings.py`.** Report the exact numbers
   (`R@1`, `bundle_full`, `p50`) in the commit message — not "still passes",
   the actual numbers, so a regression is visible in `git log` even if nobody
   ran the gate at merge time.
4. Only after that: continue with phase 8 (§6) if there's room, but fixing
   what's here takes priority over building further on top of it.

---

## 0. ⚠️ GIT — READ BEFORE TOUCHING ANYTHING

`~/megabrain-v2` has **34 tags**, a published PyPI package (`megabrain`), and a
release pipeline wired to Trusted Publishing. A fresh `git init` here destroys
all of it: tags, release notes, the version line, and the link between the repo
and its PyPI publisher config.

**FORBIDDEN:**

```bash
cd ~/megabrain-v3 && git init          # ← NEVER. This orphans 34 releases.
```

**REQUIRED — v3 is a BRANCH of the existing repo, not a new repo:**

```bash
# Option A (recommended): a worktree — v2 stays browsable while v3 is built
cd ~/megabrain-v2
git worktree add -b v3 ~/megabrain-v3 master

# Option B: a clone
git clone ~/megabrain-v2 ~/megabrain-v3 && cd ~/megabrain-v3 && git checkout -b v3
```

Then the rewrite happens **inside that branch**: delete `src/megabrain/`, build
the new tree, commit. `git log` keeps every commit, `git tag` keeps every
release, and the eventual merge to `master` is an ordinary merge — no
`--allow-unrelated-histories`, no force-push, no rewrite.

**Version continuity (non-negotiable):**

- v2 is `1.0.0`. v3 breaks public contracts → the next release is **`2.0.0`**.
- **Never reset to `0.1.0`.** PyPI versions are permanent and monotonic. A
  reset makes the package unpublishable at that number forever.
- The version lives in exactly one place: `src/megabrain/_version.py`, read by
  `pyproject.toml` dynamically. Nowhere else.
- `CHANGELOG.md` gets a `## 2.0.0 — <thematic title>` section. The GitHub
  release notes are EXTRACTED from it, never written twice.
- Do not delete `.github/workflows/*`. `release.yml` already invokes `ci.yml`
  via `workflow_call` so the tagged commit is gated — that mechanism exists
  because 0.13.0, 0.13.1 and 0.14.0 shipped with lint red. Keep it and add the
  new gates to it.

**Before the final merge, verify:**

```bash
git tag | wc -l          # must still be 34 (plus any new)
git log --oneline | wc -l  # must be >= the count before the rewrite
gh release list | head    # the published releases must still be there
```

---

## 1. Score: where megabrain stands

### Today: **7 / 10**

Genuinely strong — this is not a weak codebase, and the rewrite is not a
rescue.

| Earned | Evidence |
|---|---|
| OCP extension points | `ChunkStrategy` Protocol + `build_registry(extra=…)`; `LANES` pipeline in `scoring.py` — adding a signal is one class + one entry |
| Structured errors | `errors.py`: `code` + `http_status` + **dual inheritance** (`IndexNotFound(MegabrainError, ValueError)`) so old `except ValueError` callers keep working |
| Injectable config | `RetrievalParams` frozen+slots, travels with `SearchState` — replaced module-global monkeypatching |
| Import-time discipline | `__init__.py` lazy `__getattr__` over `_EXPORTS`; numpy/tree_sitter don't load on import |
| Derived-data versioning | `EDGE_SCHEMA = 3` forces edge re-extraction without re-embedding |
| Documentation | `ARCHITECTURE.md` + `AGENTS.md` are better than most commercial products' |
| Release pipeline | Trusted Publishing (OIDC), tag-gated, `workflow_call` from release to CI |

| Lost | Evidence |
|---|---|
| **−1.0** No type checking while shipping `py.typed` | `grep 'mypy\|pyright' pyproject.toml` → **0**. PEP 561 promises verified types to every consumer; nothing verifies them |
| **−0.7** No payload contract | `grep '\-> dict' src/megabrain` → **88**; `grep TypedDict` → **0**. The bundle — the engine's central artifact — is an untyped dict consumed by render, ask, MCP, HTTP and the studio |
| **−0.5** The #1 hard rule is not structural | `retrieval/` contains `rerank.py`, `deep.py`, `closure.py`, `mapcard.py` — all LLM callers — beside the sacred no-LLM `scoring.py`/`bundle.py` |
| **−0.4** The #2 hard rule has no versioned gate | `tests/test_engine_golden.py` and `tests/test_multi_repo.py` are **in `.gitignore`**. `bundle_full ≥ 0.90` depends on a human remembering |
| **−0.3** God-files | `graph.py` 852 · `server/http.py` 851 · `server/mcp.py` 664 · `ask/agents.py` 612 |
| **−0.1** Stated rules broken in place | `app.prune()` runs raw SQL (`app.py:219`) 100 lines above `app.stats()`, whose docstring says *"no raw SQL in the frontend — Store owns it"* |

### After this plan, executed in full: **9 / 10**

Same score I give `anthropic-sdk-python` — which is the reference. What the last
point costs, and why it isn't chased here:

- **External validity of the golden set.** The corpus is private and
  self-selected. A public benchmark (SWE-bench retrieval, CodeSearchNet) would
  make the numbers defensible to strangers. Out of scope.
- **`forge/` executes LLM-written code.** Trust-gated by sha256 against a
  user-level store, partition-oracle-verified — genuinely well designed, and
  still `exec()` of generated code. That is an accepted risk, not a solved one.

**10/10 does not exist. Do not chase it.**

---

## 2. The invariants — a change that breaks one is not merged

These are v2's five hard rules. They survive the rewrite unchanged, and in v3
three of them become **structurally enforced** instead of documented.

1. **No LLM in the retrieval path.** v3 enforces it with a test that walks
   imports (§6, phase 7). `retrieval/` may not import `providers.chat` or
   `enrich/`.
2. **Completeness beats ordering.** `bundle_full` is currently **1.00**. A
   change that lowers it is not merged. Noise is handled by render structure,
   never by dropping files.
3. **The graph never ranks.** Import/call edges supply candidates and map
   annotations only. PageRank-as-ranking was rejected by experiment (Acc@1
   0.91 → 0.73).
4. **Chunks are a line partition.** `validate_partition` clean: no gaps, no
   overlaps, full coverage.
5. **`ask` shows real code only.** The model emits `[[k]]` citations; the
   engine splices verbatim from disk. The model can never emit code.

**Parity bar for the whole rewrite:** R@1 ≥ 0.86 · **bundle_full = 1.00** ·
p50 ≈ 10 ms. v3 must match v2 on all three before any algorithm work starts.

---

## 3. TDD — the working protocol, no exceptions

**Write the test first. Watch it fail. Then implement.** Every phase, every
module, every bug fix.

```
1. RED     write the test against the CONTRACT. Run it. It must FAIL,
           and fail for the right reason (not an ImportError typo).
2. GREEN   write the minimum implementation that passes.
3. GATE    run the phase's full gate (§6). Green before the next commit.
4. COMMIT  one phase-step per commit, message says what the test pins.
```

Hard rules:

- **Never write implementation before its test exists and fails.** If you
  catch yourself doing it, delete the implementation and start over.
- **A test that passes the first time you run it is a broken test.** Make it
  fail deliberately (break the assertion, or the implementation) to prove it
  can.
- **Behaviour parity tests come from v2's actual output**, not from imagination:
  capture v2's real output as a fixture, then assert v3 reproduces it.
  ```bash
  # capture v2's ground truth BEFORE writing v3's implementation
  cd ~/megabrain-v2 && megabrain search ~/some/repo "how does X work" --json \
    > ~/megabrain-v3/tests/fixtures/parity/search_X.json
  ```
- **`filterwarnings = ["error"]` and `xfail_strict = true` from phase 0.** A
  new deprecation fails the suite the day it appears.
- Tests live in `tests/` mirroring `src/` 1:1. A module without a test file is
  an incomplete phase.

---

## 4. The reference implementation — query it, don't guess

`~/experiments/anthropic-sdk-python` is indexed in megabrain. **When a pattern
is unclear, query it instead of inventing.** That repo is the 9/10 this plan
targets.

### How to run it (there is a trap)

That repo pins `.python-version = 3.9.18`, which is not installed, so `cd`-ing
into it breaks the `megabrain` shim. **Always run from `~/megabrain-v2` (or
v3) with an absolute path:**

```bash
cd ~/megabrain-v2                 # never cd into the anthropic repo
megabrain ask ~/experiments/anthropic-sdk-python "<question>"
# fallback if the shim still misbehaves:
~/.pyenv/versions/3.11.0/bin/megabrain ask ~/experiments/anthropic-sdk-python "<question>"
```

### The queries to run, per phase

| When you are unsure about… | Run |
|---|---|
| Sentinels / three-state params | `megabrain search ~/experiments/anthropic-sdk-python "NotGiven Omit sentinel strip_not_given"` |
| Typed payloads across boundaries | `megabrain ask ~/experiments/anthropic-sdk-python "how do TypedDict params carry their wire contract through maybe_transform?"` |
| Lenient vs strict deserialization | `megabrain ask ~/experiments/anthropic-sdk-python "how does construct_type resolve a discriminated union without validating?"` |
| Retry policy | `megabrain ask ~/experiments/anthropic-sdk-python "how does the retry loop decide what is retryable and how long to wait?"` |
| The middleware seam | `megabrain ask ~/experiments/anthropic-sdk-python "how does the middleware chain interact with the retry loop?"` |
| Streaming layers / events | `megabrain ask ~/experiments/anthropic-sdk-python "how does the SSE decoder feed the typed stream and the message accumulator?"` |
| Multi-backend hooks (for our transports) | `megabrain ask ~/experiments/anthropic-sdk-python "how does the Vertex client rewrite the URL and inject auth without touching resources?"` |
| Error hierarchy | `megabrain search ~/experiments/anthropic-sdk-python "APIStatusError status_code Literal request_id"` |
| Lazy imports / import time | `megabrain grep ~/experiments/anthropic-sdk-python cached_property` |
| Test conventions | `megabrain ask ~/experiments/anthropic-sdk-python "how are the client tests structured and what does strict response validation do in them?"` |

Also read directly: `~/.claude/skills/art-of-python/PATTERNS.md` (the deep
reference) and `~/.claude/skills/art-of-python/example/` (a runnable 54-test
mini-SDK — copy its shapes).

---

## 5. v2, file by file — the dependency map

**Read this table before writing a single line.** It is the whole of v2:
58 files, 13 878 LOC — 49 modules plus 9 `__init__.py` re-export shims (the
shims are not itemized; each one just re-exports its package's public names).
`→` is the v3 destination. Risk is how likely a behaviour regression is if you
rewrite it carelessly.

### Root

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `__init__.py` | 72 | Lazy public API: `__getattr__` over `_EXPORTS`. **Keep this pattern verbatim** | `__init__.py` | low |
| `__main__.py` | 6 | `python -m megabrain` | `__main__.py` | none |
| `app.py` | 399 | Use-case layer, one function per verb. `prune()` alone is 165 lines with 7 responsibilities + raw SQL | `usecases/*.py`, one file per verb | **high** |
| `errors.py` | 77 | The taxonomy. Dual inheritance for back-compat. **Port nearly as-is** | `_errors.py` | low |
| `model.py` | 42 | `ChunkMeta` | `contracts/chunk.py` | low |
| `graph.py` | 852 | The knowledge graph (numpy): communities, god nodes, surprises, BFS paths, cached LLM labels | `knowledge/{build,communities,paths,render}.py` | med |
| `mcp_server.py` | 8 | Entry shim | `transports/mcp/__main__.py` | none |

### `chunkers/` — content → FileResult (1 173 LOC)

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `base.py` | 91 | **THE contract**: `Chunk`/`Symbol`/`FileResult`/`validate_partition`/`embed_text`. Invariant #4 lives here | `contracts/chunk.py` (types) + `chunkers/base.py` (helpers) | low |
| `cast.py` | 107 | The shared split-then-merge engine (cAST, arXiv 2506.15655) | `chunkers/cast.py` | med |
| `python.py` | 317 | stdlib `ast` chunker | `chunkers/python.py` | med |
| `treesitter.py` | 470 | The same algorithm parameterized by `LangSpec`: TS/JS, Ruby, Go, Rust, PHP | `chunkers/treesitter/chunker.py` + `specs/<lang>.py` (one file per language) | med |
| `php.py` | 264 | Shape-routed PHP: modern vs legacy-2000s procedural | `chunkers/php.py` | med |
| `markdown.py` | 224 | No-LLM doc chunker: scored cut lines (H1=100…H6=50, fence=80, para=20) | `chunkers/markdown.py` | med |
| `__init__.py` | 26 | Re-exports | — | none |

### `indexing/` — walk → chunk → embed → store (1 387 LOC)

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `indexer.py` | 302 | The pipeline. 3 phases already marked `# PHASE 1/2/3` — the global-batch embed is what took a cold index from ~20 min to seconds. `maybe_reindex` = 60 s TTL, fail-open | `indexing/indexer.py` (orchestration) + `discover.py`; the 3 phases become 3 functions | **high** |
| `strategies.py` | 355 | The OCP registry + `ChunkStrategy` Protocol + `EDGE_SCHEMA` + trust-gated repo-local loading | `indexing/strategies.py` + `indexing/trust.py` | **high** |
| `graph.py` | 409 | Edge extractors: python/ts/ruby/go/php import+call resolution | `indexing/edges/<lang>.py` | med |
| `ignore.py` | 319 | `.megabrainignore`, gitignore matcher, vendored/generated detection, `scan` census | `indexing/discover.py` + `indexing/ignore.py` | low |

### `retrieval/` — the engine (2 425 LOC). **Split by LLM/no-LLM in v3.**

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `params.py` | 59 | `RetrievalParams` frozen. **Every default is an experiment result — port the numbers AND their comments verbatim** | `retrieval/params.py` | **critical** |
| `state.py` | 83 | `SearchState`: warm matrices + lazy issue lanes + flow cache | `retrieval/state.py` | low |
| `scoring.py` | 344 | `score_chunks` = the LANES pipeline (dense+file fusion → test penalty → issue → lexical). Single source of truth for chunk scoring | `retrieval/scoring/pipeline.py` + `lanes/*.py` | **critical** |
| `bundle.py` | 409 | Rank + tier + the two floors (recall floor, anchor floor). `selection()` is THE definition of what retrieval chose | `retrieval/bundle/{assemble,floors,select}.py` | **critical** |
| `render.py` | 378 | Bundle → markdown code map, with the token budget | `retrieval/render/{markdown,budget}.py` | med |
| `issue.py` | 129 | Long-query mode: traceback parsing, pin tiers, query variants | `retrieval/lexical/issue.py` | med |
| `bm25.py` | 57 | Sparse entity-ID lane (issue mode only) | `retrieval/lexical/bm25.py` | low |
| `grepx.py` | 215 | Literal search resolved to symbols + roles (DEFINES/READS/CONFIG/TESTS/DOCS) | `retrieval/lexical/grep.py` | med |
| `files.py` | 39 | `get_code` — one file or symbol | `retrieval/project/files.py` | low |
| `readx.py` | 180 | `megabrain_read` — batch span reads | `retrieval/project/read.py` | low |
| `replacex.py` | 123 | `megabrain_replace` — transactional batch edit | `retrieval/project/replace.py` | med |
| `docsearch.py` | 153 | The docs lane | `retrieval/project/docs.py` | low |
| **`rerank.py`** | 345 | **LLM judge** — drops vocabulary-only matches, reorders | **`enrich/rerank.py`** | med |
| **`deep.py`** | 199 | **LLM multi-turn retriever** with internal tools | **`enrich/deep.py`** | med |
| **`closure.py`** | 281 | **LLM facet-critic fan-out** (fallback for deep) | **`enrich/closure.py`** | med |
| **`mapcard.py`** | 383 | **LLM term expander** (`expand_pool`) | **`enrich/expand.py`** | med |

> The four bold rows are why the #1 hard rule is not structural today. In v3
> they live in `enrich/`, whose contract is **`Bundle → Bundle`**: every
> enricher takes the deterministic bundle and returns one that is equal or
> better. Fail → return the input. The deterministic floor cannot drop.

### `ask/` — the narrated walkthrough (1 439 LOC)

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `agents.py` | 612 | v2 pipeline: classifier → planner → parallel sub-agents → synthesizer. `stream_events` drives every surface | `ask/agents/{classify,plan,workers,synthesize}.py` | **high** |
| `narrator.py` | 535 | The walkthrough + `_Splicer` — invariant #5 lives here | `ask/narrator.py` + `ask/splice.py` | **high** |
| `warmup.py` | 275 | Flow pre-caching + derived starter questions | `ask/warmup.py` | low |
| `__init__.py` | 17 | `ask` / `render_ask` / `stream_ask` | `ask/__init__.py` | none |

### `storage/` (652 LOC)

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `store.py` | 305 | SQLite. **Sole owner of SQL.** Schema + incremental sha + flows + stats | `storage/store.py` + `storage/schema.py` | **high** |
| `flows.py` | 254 | Flow cache: cached ask syntheses, attach/serve lanes | `storage/flows.py` | med |
| `registry.py` | 92 | Machine-global repo registry (`~/.megabrain`) | `storage/registry.py` | low |

### `providers/` (936 LOC) — **split by layer in v3**

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `embeddings.py` | 214 | OpenAI-compatible `/embeddings`, int8-base64 wire, content-addressed disk cache, concurrency | **`providers/embeddings.py` (L2)** | **high** |
| `__init__.py` | 518 | Chat routing, model selection, fallback, retries | **`providers/chat/router.py` (L4)** | **high** |
| `claude.py` | 155 | Claude Agent SDK provider (`MEGABRAIN_CHAT_PROVIDER=claude`) | `providers/chat/claude.py` | med |
| `base.py` | 49 | Provider protocol | `providers/chat/base.py` | low |

### `forge/` — self-authored chunkers (905 LOC)

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `coverage.py` | 342 | LLM writes a `ChunkStrategy`; accepted only if it partitions every matching file cleanly; ≤3 repair attempts | `forge/coverage.py` | med |
| `specialize.py` | 248 | Shape detection (table/blob/line-window) — **no LLM** | `forge/specialize.py` | low |
| `ab_gate.py` | 298 | Measures a hand-written candidate against a literature baseline — **no LLM** | `forge/ab_gate.py` | low |

### `server/` — the transports (2 213 LOC)

| File | LOC | What it is | → v3 | Risk |
|---|---|---|---|---|
| `http.py` | 851 | serve-api + studio host + SSE + readonly/rate-limit/trust-proxy | `transports/http/{app,routes/*,sse,security}.py` | **high** |
| `mcp.py` | 664 | MCP stdio server + tool schemas | `transports/mcp/{server,tools,dispatch}.py` | **high** |
| `cli.py` | 484 | Argparse + TTY rendering | `transports/cli/{main,commands/*,render/*}.py` | med |
| `install.py` | 160 | `megabrain install` (MCP config into hosts) | `transports/install.py` | low |
| `session.py` | 52 | Server session state | `transports/http/session.py` | low |
| `ui/` | **3 248** | **The studio: hand-written `app.js` (2 476), `index.html` (433), `api.js` (135), `mock.js` (204). Zero build tooling — no package.json, no bundler, no types, no tests** | **`studio/` — its own TS workspace, built into `server/ui/`** | **high** |

---

## 6. The phases

Each phase: **write the tests → watch them fail → implement → gate → commit.**
Do not start phase N+1 with phase N's gate red.

### Phase 0 — scaffold ✅ DONE (`75517c4`)

Build `pyproject.toml` (copy the annotated one from
`~/.claude/skills/art-of-python/STRUCTURE.md` §2), `scripts/{bootstrap,format,lint,test,gates}`,
`py.typed`, CI with **ruff + mypy + pyright**, one dummy test.

- `scripts/lint` = `ruff check . && mypy && pyright`.
- pyright `pythonVersion = "3.10"` (the oldest supported, not the newest).
- mypy starts permissive with a per-module opt-in list; each phase adds its
  modules. **The list only grows.**
- Keep `.github/workflows/release.yml` and its `workflow_call` into `ci.yml`;
  add `typecheck` to the gated jobs.

**Gate:** CI green. `git tag | wc -l` still 34.

### Phase 1 — L0 vocabulary ✅ DONE (`75517c4`)

`_types.py` (`NotGiven`/`not_given`/`Omit`/`omit`/`is_given`), `_errors.py`
(port v2's taxonomy incl. the dual inheritance), `_constants.py`, `_utils/`.

- Sentinels first: v2 has **80** `X | None = None` params and a hand-rolled
  tri-state (`app.normalize_agents`: `None | "auto" | bool`). That function
  **is** a `NotGiven` written by hand — replace it.
- ⚠️ The trap documented in `PATTERNS.md` §1: `is_given()` rejects both
  sentinels, but `strip_not_given()` must strip **only `NotGiven`** — an `Omit`
  in a headers/params mapping still has work to do downstream.

**Tests first:** the three states produce three different outcomes; `Omit`
removes a default; `repr(not_given) == "NOT_GIVEN"`.
**Gate:** mypy+pyright strict clean on `_*`; no I/O in this layer.

### Phase 2 — L1 `contracts/` ← **the pivot of the whole rewrite** ✅ DONE (`4f7b346`)

**All payloads, defined before a single implementation exists.**

`contracts/{chunk,index,bundle,ask,graph,grep}.py`. `TypedDict` only —
**not** dataclasses, **not** pydantic:

- At runtime a `TypedDict` **is** a `dict` → zero cost, zero new dependency,
  and every existing consumer (`res["chunks"]`, the studio's JSON, the MCP
  payloads) keeps working unchanged.
- Dependencies stay `numpy + tree_sitter + tree_sitter_typescript`. That
  thinness is a product feature.

Discriminated unions for the event streams (`ProgressEvent`, `AskEvent`),
keyed by `type` — the exact shape the reference SDK uses:

```bash
megabrain ask ~/experiments/anthropic-sdk-python \
  "how are streaming events typed as a discriminated union and dispatched?"
```

**Tests first:** for each contract, a test asserting the real v2 payload
(captured as a fixture) type-checks against it. That is how you discover the
optional keys nobody documented — `setaside`, `related_docs`, `related_tests`.
**Gate:** every fixture in `tests/fixtures/parity/` validates.

### Phase 3 — L2 storage ✅ DONE (`7561799`)

`storage/{store,schema,flows,registry}.py`. `schema.py` owns DDL + versioned
migrations. **`Store` is the only module in the entire codebase allowed to
write SQL** — enforce with a test that greps for `db.execute` outside
`storage/`.

**Gate:** round-trip tests against an in-memory sqlite; the SQL-locality test.

### Phase 4 — L2 embeddings ✅ DONE (`1ab2ec6`, fixed further in `68cc934` — see STATUS)

`providers/embeddings.py` + `providers/_http.py` (retry, backoff,
`Retry-After`, `__cause__` chain walk — copy the reference's policy).

```bash
megabrain ask ~/experiments/anthropic-sdk-python \
  "how does the retry loop decide what is retryable and how long to wait?"
```

**Tests first:** with a fake transport — 429→200 retries once; 4xx doesn't
retry; a wrapped retryable error still retries; the content-addressed cache
avoids a second call. **No network in any test.**

### Phase 5 — L3 chunkers ✅ DONE (`c40c8c2`)

`base` → `cast` → `python` → `treesitter/chunker` + `specs/` → `markdown` →
`php`.

**Tests first, and the test is the invariant:** `validate_partition` clean over
a real corpus, per language. v2's chunker tests
(`test_cast_chunker`, `test_chunker_ts`, `test_markdown_chunker`,
`test_php_chunker`, `test_php_legacy_chunker`, `test_cast_unification`) are the
spec — port them before the implementations.

**Gate:** zero partition violations indexing 5 real repos of different languages.

### Phase 6 — L3 indexing ✅ DONE (`49ce49d`)

`discover` → `strategies` (+`trust`) → `edges/` → `indexer` (3 phases = 3
functions).

- Preserve the global-batch embed: chunk everything first, embed **once**.
  Per-file embedding was ~2 HTTP round trips per changed file (~20 min cold on
  a rails-sized repo).
- Preserve `EDGE_SCHEMA` and bump it if any extractor changes.
- POSIX relpaths everywhere (`as_posix()`, never `str(path)`); explicit
  `encoding="utf-8"` on every read/write. **Windows is a first-class CI target.**

**Gate:** `IndexStats` byte-identical to v2 on 3 real repos.

### Phase 7 — L3 retrieval ← **the highest-risk phase** ✅ DONE (`fbcbc9a`) — see STATUS for what's not yet ported

`params` → `state` → `scoring/{pipeline,lanes/*}` → `bundle/{assemble,floors,select}`
→ `render` → `lexical/*` → `project/*`.

**Rules for this phase specifically:**

- **Port the arithmetic and the comments verbatim.** Every constant is an
  experiment result: `file_fusion_w = 0.5` ("phase 3 winner"), `graph_extras`
  retuned 6→7 after the edge-preservation fix, `anchor_df_cap = 10`. The field
  cases in the comments (nx#35656: the exact precedent at raw-dense rank 13 of
  10 891 that fusion pushed to 81; attrs#1549: `_CountingAttr.default` at
  in-file rank 16 of 27 near-ties) **are the specification**. Losing them loses
  the reason the code is shaped that way.
- **The two floors are pure additions** — they never rank, never displace.
  `bundle_full` can only rise. Keep that property.
- **The no-LLM enforcement test** ships in this phase:

```python
# tests/contracts/test_no_llm_in_retrieval.py — write this FIRST
def test_retrieval_never_imports_an_llm():
    for module in walk("src/megabrain/retrieval"):
        imports = imports_of(module)
        assert "providers.chat" not in imports, f"{module} breaks hard rule #1"
        assert "enrich" not in imports, f"{module} breaks hard rule #1"
```

**Gate (all four, every commit in this phase):**
`bundle_full = 1.00` · R@1 ≥ 0.86 · p50 ≈ 10 ms · the no-LLM test.

Also in this phase: **the golden gate becomes versioned.** Build
`evals/harness/` (the runner, committed) + `evals/corpus/` (a small public
corpus, 5–8 repos with vectors, committed) so CI can run `bundle_full` on
every PR. The big private corpus stays in `evals/private/` (gitignored). Today
`tests/test_engine_golden.py` is gitignored — the engine's #2 rule has no
versioned gate at all. **Fixing that is part of this phase, not a follow-up.**

### Phase 8 — L3 knowledge (the graph) — NOT STARTED

Split `graph.py` (852) into `knowledge/{build,communities,paths,render}.py`.
**The graph never ranks** — it supplies candidates and annotations only.

### Phase 9 — L4 chat + `enrich/` — NOT STARTED

`providers/chat/{router,openai_compat,claude}.py`, then `enrich/{expand,rerank,deep,closure}.py`.

**The `enrich` contract is one line: `Bundle → Bundle`.** Every enricher is
opt-in and fail-open; on any failure it returns its input unchanged.

**Tests first:** for each enricher — provider raises → the input bundle comes
back identical. That test is the hard rule, executable.

### Phase 10 — L4 ask — NOT STARTED

`narrator` + `splice` + `agents/` + `stream`.

The event stream is the three-layer streaming pattern; consult the reference:

```bash
megabrain ask ~/experiments/anthropic-sdk-python \
  "how does the SSE decoder feed the typed stream and the message accumulator?"
```

**Tests first:** invariant #5 — feed the narrator a model response containing
fabricated code and assert **none of it** reaches the output; only spliced
disk bytes do. Port `test_ask_citation`, `test_ask_modes`,
`test_ask_v2_integration`.

### Phase 11 — L5 `usecases/` — NOT STARTED

One file per verb. Decompose `app.prune()` (165 lines, 7 responsibilities) into
`prune.py` + the helpers it calls. **The test-file scan moves into `Store`** —
no raw SQL outside `storage/`.

**Gate:** behaviour parity with v2 on the captured fixtures.

### Phase 12 — CLI · Phase 13 — MCP · Phase 14 — HTTP — NOT STARTED

In that order (cheapest surface first, and each validates the use-case layer
before the next).

- MCP tool schemas are **generated from `contracts/`** — one definition, not two.
- HTTP: `transports/http/{app,routes/*,sse,security}.py`. Async only at this
  edge; it calls the **sync** use-cases in a threadpool.
- **Never `asyncio.run()` inside the engine.** megabrain is numpy + sqlite; it
  does not need and must not have an async twin. That is what saves v3 from the
  duplication tax the reference SDK pays (~600 duplicated lines per client).

**Gate:** `test_mcp_tools_golden`, `test_serve_api_ui`, `test_studio_boot`, e2e CLI.

### Phase 15 — the studio — NOT STARTED

`studio/` as its own TypeScript workspace (esbuild), with `studio/src/api/`
typed against `contracts/` — the same contract the MCP serves. Build output
goes to `src/megabrain/server/ui/`.

**Decision required from Berna before starting:** is the built bundle
committed?

| | committed | generated at release |
|---|---|---|
| `pip install -e .` from a clone without node | works | **breaks** |
| PR diffs | bundle noise | clean |
| failure mode | goes stale | release forgets to build |

Recommended: **commit it + a CI job that rebuilds and fails if the diff is
non-empty.** Both benefits, no drift.

**Gate:** studio boots; the 25-assertion smoke test from
`bernardocastro.dev/services/megabrain/` passes (every assertion in it came
from a real outage).

### Phase 16 — forge — NOT STARTED

`coverage` (LLM, partition-gated) + `specialize` + `ab_gate` (both no-LLM).
Last because it depends on `chunkers` + `indexing` + `providers/chat`.

### Phase 17 — **algorithm improvements** (only after full parity) — NOT STARTED, and not eligible until 8–16 land

**Do not touch the algorithm before phase 16's gate is green.** Refactoring and
re-tuning at the same time makes a regression unattributable — you will not know
whether the number moved because of the rewrite or the idea.

Protocol, one hypothesis per PR:

1. **Pre-register** the hypothesis in the PR description: what changes, what
   metric should move, by how much, and what would falsify it.
2. Implement behind a `RetrievalParams` field (frozen, injectable) so it is a
   config variant, not a fork.
3. Measure against the golden with the flag off and on. Report both numbers.
4. **Merge only if `bundle_full` does not drop.** Completeness beats ordering —
   an idea that improves R@1 while losing a file is rejected.
5. Record the result in `CHANGELOG.md` with the numbers, including negative
   results. The rejected experiments (LLM pruning tried four ways; PageRank
   ranking, Acc@1 0.91 → 0.73) are as valuable as the accepted ones.

---

## 7. Forbidden

- `git init` in this directory. Ever. (§0)
- Resetting the version below `1.0.0`.
- Deleting `.github/workflows/` or the `workflow_call` gate chain.
- Adding a runtime dependency. The three (`numpy`, `tree_sitter`,
  `tree_sitter_typescript`) are a product feature.
- Converting the payload dicts to dataclasses or pydantic models — it breaks
  every consumer for no runtime gain. `TypedDict` or nothing.
- Writing implementation before its failing test exists.
- Tuning a constant during the rewrite. Port the number and its comment;
  re-tune in phase 17 with a pre-registered hypothesis.
- An LLM import inside `retrieval/`.
- `asyncio.run()` anywhere inside the engine.
- Raw SQL outside `storage/`.
- `assert` for a production invariant — `python -O` deletes it. Raise a real
  error.

---

## 8. Definition of done

- [ ] `git tag | wc -l` ≥ 34; `gh release list` intact; the v3 branch merges to
      `master` as an ordinary merge.
- [ ] `scripts/lint` clean: ruff + mypy + pyright, all strict, every exclusion
      named and justified in `pyproject.toml`.
- [ ] `scripts/test` green on the CI matrix (3 OS × 4 Python).
- [ ] `scripts/gates` green **in CI**, not just locally: `bundle_full = 1.00`,
      R@1 ≥ 0.86, p50 ≈ 10 ms.
- [ ] `grep -r '\-> dict' src/megabrain` → every remaining one is deliberate and
      typed; `contracts/` covers every cross-boundary payload.
- [ ] The no-LLM-in-retrieval test passes.
- [ ] The SQL-locality test passes.
- [ ] The studio builds from `studio/` and boots; the 25-assertion smoke passes.
- [ ] `ARCHITECTURE.md` and `AGENTS.md` describe v3, not v2. A doc that lies is
      a bug.
- [ ] `CHANGELOG.md` has a `## 2.0.0 — <title>` section written from the real
      diff, including what was intentionally dropped.
