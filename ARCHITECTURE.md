# megabrain — Architecture

This document is written **from the source**, not from intent: every claim below
names the module that implements it, and the invariants are the ones the test
suite actually enforces (`tests/architecture/` fails the build when one breaks).

```
question ──► embed (1 call, cached) ──► score (numpy, no LLM) ──► Bundle
                                                                    │
                       ┌────────────────────────────────────────────┤
                       ▼                    ▼                       ▼
                     grep                  ask                   search
              (edit surface, no LLM)  (narrated, spliced)   (the map / docs)
```

---

## 1. The five hard rules

Each one is executable, not aspirational:

| # | rule | enforced by |
|---|---|---|
| 1 | **No LLM in the retrieval path.** Nothing under `search/` or `grep/`'s lanes may import `providers.chat` or `enrich/` | an import-walking test |
| 2 | **Completeness beats ordering.** Recall floors only ever *append*; a change lowering `bundle_full` is not merged | the golden gate (`evals/harness/gate.py`) |
| 3 | **The graph never ranks.** Edges supply candidates and evidence only (PageRank-as-ranking: Acc@1 0.91 → 0.73, rejected) | the assembly-only split in `graph/views.py` |
| 4 | **Chunks are an exact line partition.** No gaps, no overlaps, full coverage | `validate_partition` — the same oracle that gates generated chunkers |
| 5 | **The model never emits code.** It cites `[[k:lo-hi]]`; the engine splices verbatim bytes from the index | `ask/citing/splice.py` — fenced blocks in a model reply are *deleted* |

Plus the structural ones: SQL only inside `storage/`, no `asyncio.run()` inside
the engine, no `assert` in shipped code, L0 imports nothing, every file ≤100
lines and every function ≤30 — all parametrised tests.

---

## 2. Layering

Lower layers never import higher ones; the architecture suite walks the imports.

```
L0  vocabulary      _types  _arrays  _errors  _provider_errors  _version
                    _home  _models  _config_file  project.py
L1  contracts/      every cross-boundary payload — TypedDict only
L2  storage/        the ONLY package that writes SQL
    providers/      http/ · embeddings/          (chat/ is L4 — see §7)
L3  chunkers/       content → chunks (partition-guaranteed)
    indexing/       walk → chunk → embed → store
    search/         scoring · bundle · render — deterministic
    graph/          build · clusters · routes · symbols
L4  enrich/         opt-in model lanes, contract: Bundle → Bundle, fail-open
    converse/       the shared model loop (open_file), prompt building,
                    backend resolution — neutral ground between the verbs
    ask/            the narrated walkthrough
    grep/           the edit surface — no model in the lanes
    flows/          the cached-walkthrough lane
    forge/          strategies the machine writes (oracle-gated) or measures
L5  usecases/       the verbs no feature owns + re-exports
    transports/     cli/ · mcp/ · http/ (+ built studio) · install/
```

Two deliberate placements worth naming:

- **`providers/chat/` is L4** even though it lives under `providers/`: it is
  fenced from retrieval by the rule-1 test. `providers/embeddings/` is L2
  because retrieval depends on it — an embedding is a pure function of its
  text, which is what makes it deterministic and cacheable.
- **`grep/` is a top-level package**, not a submodule of `ask/`, so "grep's
  lanes call no model" is an *importable* fact a test can check — `ask/`
  imports a chat provider by design, so nothing inside it can be fenced.
  What the two verbs share — the open_file conversation loop, the
  candidate/chunk-block prompt building, the backend resolution — lives in
  **`converse/`**, which imports neither verb; `grep/` never imports `ask/`
  at all, and both facts are architecture tests.

Packaging is **by domain, not by layer** (`docs/DOMAINS.md`): each verb lives
beside its own logic (`search/search.py`, `grep/grep.py`), and `usecases/`
keeps only what no feature owns (`resolve_root`, `repos`, `scan`, `get`).

---

## 3. L0 — the vocabulary

| module | what it is |
|---|---|
| `_types` | the three-state sentinels (`NotGiven`/`not_given`, `Omit`/`omit`, `is_given`) and `Content = Literal["code","docs"]`. Only an *omitted* credential reads the environment; an explicit `None` means "no key" and fails loudly |
| `_arrays` | named numpy aliases — `Vector`, `Matrix`, `IndexArray`, `BoolMask`. float32 end to end; naming the dtype stops a float64 promotion from silently doubling the hottest matrix |
| `_errors` | the engine taxonomy: `MegabrainError` root, each subclass carrying a stable machine `code` + `http_status`, **dual-inherited** from the builtin a pre-typed caller would have caught (`IndexNotFound(MegabrainError, ValueError)`) |
| `_provider_errors` | the environment half (`ProviderError` with optional upstream `status`, `MissingCredential`) — split out because L0 may import nothing and these sit one layer up |
| `_home` | `megabrain_home()`: `$MEGABRAIN_HOME` or `~/.megabrain` — one answer for machine-global state, injectable so tests never touch the real home |
| `_models` | the default model per **job** (`NARRATOR_MODEL`, `RERANK_MODEL`, `CLAUDE_NARRATOR_MODEL`) — one constant per lane, because sharing one model between jobs is what made the judge take 16 s |
| `_config_file` | lenient JSON reading for files a human edits: take what's valid, ignore what isn't, never let one wrong field take the file down |
| `project.py` | `megabrain.json` — the repo's committed config: `ignore`, `queries`, `gitignore`, `models.{narrator,rerank,provider}`. A committed file travels with the clone; an env var doesn't |

`__init__.py` is a lazy `__getattr__` over `_EXPORTS`: `import megabrain` loads
no numpy and no tree_sitter (pinned by a test that inspects `sys.modules`).

---

## 4. L1 — `contracts/`

Every payload that crosses a boundary, declared once, as **TypedDict** — at
runtime these *are* dicts, so the wire format is the same object serialised and
the engine gains no dependency. Verified against **captured real payloads**
(`tests/fixtures/parity/`), never against what the producing code looks like.

| contract | notes |
|---|---|
| `Bundle` | `tier1: Tier1File[]` (CORE, full chunks), `tier2: Tier2File[]` (RELATED, a map), `flows`, `anchors`, `judge: {kept, of} \| None`, `evidence: strong\|weak\|none`, `top_cosine`, `expanded`, `ms`. Six consumers: render, ask, CLI, MCP, HTTP, studio |
| `ChunkRef` vs `ChunkHit` | load-bearing: a tier-2 `best_chunk` carries **no score** — the *file* was ranked, not that span. Modelling that as one optional field lets a scoreless span reach code that sorts by score |
| `PruneResult`, `FileView`, `ScanReport`, `RepoEntry`, `HostRow/HostResult` | the flat projection, `get` (with the `stale` flag — the indexed text is what the ranking saw), `scan` (every skip with its reason), the registry, `install` |
| `GraphMap` / `NodeView` / `Neighbourhood` / `GraphPath` (`Hop`, `HopCode`, `CodeSnip`) | the graph as drawn vs as read; `GraphPath.chain/meet/meet_kind` is the honesty field — a shared callee is a meeting, not a flow |
| `AskParams`, `GrepParams`, `SearchParams`, `NodeParams`, `IndexParams` (`contracts/tools/`, split read vs write) | the MCP `inputSchema` is **generated** from these — one definition, and every `Annotated` description is agent-facing documentation distilled from measured sessions |

Optionality is spelled with the **`total=False` split, never `NotRequired`**:
under `from __future__ import annotations` TypedDict can't see the marker and
`__optional_keys__` comes back empty (`tests/contracts/test_optionality.py`
pins the trap). The shape checker itself has an adversarial suite —
bool-is-not-int, dict value types checked, unknown annotation forms fail
*closed*.

---

## 5. L2 — storage and the deterministic providers

### `storage/` — the only SQL in the codebase

One SQLite file per repo at `<repo>/.megabrain/db.sqlite`. `Store` owns the
connection; each table is its own object:

```
Store
 ├─ files    FileTable     path · sha256 · skeleton text · skeleton vector
 ├─ chunks   ChunkTable    the partition + per-chunk vectors (float32 BLOBs)
 ├─ symbols  SymbolTable   qualified names, kinds, line ranges, signatures, docs
 ├─ graph    GraphTable    edges (src, dst, kind ∈ import|call|pins) + meta k/v
 └─ flows    FlowTable     cached walkthroughs + two vectors each (attach/serve)
```

- `schema.py` owns DDL + late-column migrations, applied idempotently on every
  open; only "duplicate column" is tolerated — a locked database *raises*.
- `Store.__exit__` **commits on clean exit, rolls back on exception**. The
  audit found the original block closing without committing: a full index that
  reported success and wrote nothing.
- Vectors load into **one numpy matrix**; row *i* belongs to `metas[i]` — the
  alignment is the whole contract. Brute-force cosine is <2 ms up to ~50 K
  chunks, so ANN is deliberately deferred.
- Relpaths are **POSIX everywhere**; a backslash key is index corruption that
  only shows as everything silently failing to match. Windows is a first-class
  CI target for exactly this class of bug.
- `locate.resolve_root()` walks upward like git; the `.megabrain/db.sqlite`
  path exists in exactly one line (`INDEX_FILE`).
- `_locking.BUSY_TIMEOUT`: MCP is stdio, every editor session is its own
  process, so multi-process access is structural — readers never wait, a
  second writer queues instead of dying at Python's 5 s default. SQLite
  restarts the busy handler per lock handoff, so the timeout bounds one
  holder, never the queue.
- `model.ChunkMeta` is a frozen slotted **dataclass**, not a TypedDict: it
  never leaves the process, attribute access wins on the hot path, and the
  vector is deliberately absent (it lives in the matrix).
- `symbols.find()` escapes `_`/`%` before its LIKE arm — Python is made of
  underscores, and unescaped, `get_meta` also matched `getXmeta`.

### `providers/http/` — one retry policy for everything

`Transport` is a Protocol (`send` + `open` for streaming). `RetryPolicy`
honours `Retry-After` (ms variant preferred, absurd values ignored, honoured
values **not** clamped by the backoff ceiling), jitters downward only, keeps
the original `__cause__`, and **stops retrying once the caller has seen
output** — a retried stream prints the answer twice.

### `providers/embeddings/` — text → unit float32 vectors

`Embedder` = codec + batching policy + cache, the split invisible from outside:

- **Batching by size, not count** (`_batching`, `_budget`): `CHARS_PER_TOKEN =
  2.0`, deliberately conservative (measured 2.54 on Python, 1.47 on dense
  generated content). Being wrong downward costs one extra round trip; upward
  it once failed a whole index.
- **Oversize recovery** (`_send`, `_oversize`): a size refusal splits the
  batch and retries (bounded, `MAX_SPLITS = 5`); a single oversize text is
  clipped rather than failing the repository over one file.
- **Wire decoding** (`_wire`, `_width`): the `index` SET is validated (not
  just sorted — `[0,0,2]` sorts fine and misassigns), int8-vs-float32 width is
  decided **per batch by consensus** (per-row detection misreads ~1/200 and a
  cold index caches the garbage forever), dimensions must be uniform, and
  normalisation skips zero vectors (a NaN poisons every score silently).
- **Errors keep the endpoint's words** (`_replies`): gateways refuse with
  HTTP 200 + `{"error": …}`; the body is quoted, because
  `unexpected shape: 'data'` once cost an afternoon.
- **Cache** (`cache.py`): content-addressed on sha256(model + text) under
  `~/.megabrain/embeddings`, two-char sharded, atomic-rename writes; a
  zero-byte file (post-power-loss) is a *miss* and is unlinked. The model is
  part of the key — two models are two vector spaces.

---

## 6. L3 — chunkers, indexing, search, graph

### `chunkers/` — content → a guaranteed partition

The cAST recipe (arXiv 2506.15655): **split what is too big, merge what is too
small**, budgeted in non-whitespace characters (`DEFAULT_BUDGET = 4000`) so
indentation isn't punished.

```
Chunker(parse: ParseFn)
  cover()     every line owned by exactly one span; the gap BEFORE a unit
              belongs to it (a docstring banner is about its function)
  split()     structural first (a container splits at its members, the header
              region kept as a unit and re-split), by-weight fallback with
              balanced cuts (_balance — greedy filling reintroduces the
              no-signal fragment merge exists to avoid)
  merge()     adjacent small spans fold up to the budget; split fragments never
  renumber()  consecutive fragments stamped "k/n" once the recursion finishes
```

A language contributes a `ParseFn` (source → `Parsed(units, symbols, skeleton,
ok)`) and nothing else:

- **Python** — stdlib `ast`; lines split on `\n` **only** (`splitlines()`
  breaks on `\f`/`\v` and desyncs from ast's line model — silent span
  corruption); decorators pull a definition's start line up; typed constants
  (`MAX: int = 10`) are symbols too.
- **TypeScript / JS / TSX / JSX** — one tree-sitter grammar; `unwrap_exports`
  (or a modern TS file appears to declare nothing), `assign_defs`
  (`Route.prototype.dispatch = fn` — how half of npm declares its API), and
  `called_block`: a mocha/jest `it('…', fn)` becomes a symbol carrying its own
  line range, while `describe` is recursed but never recorded — recording the
  group would swallow every case inside it.
- **Ruby, Go, Rust, PHP, C, C++, Java, C#** — the same walk bound to a
  `LangSpec` **table** (`treesitter/specs/`): a language is data, not a class.
  Grammars are optional extras; a missing one degrades to line windows, never
  to an unindexable repo. Unit end lines are clamped to the file (a grammar
  half-reading a file can report a node one line past the content).
- **Markdown** — headings as units (fences and front-matter respected), the
  skeleton is the table of contents.

Two embedded granularities: **chunk vectors** (breadcrumb + code — contextual
retrieval; the breadcrumb is prepended for embedding only, the stored text
stays verbatim) and **file skeletons** (declarations + first doc lines, one
vector per file — the fusion signal in §6-search).

### `indexing/` — three phases, one transaction

```
discover ─► plan (sha256 diff, pure CPU) ─► embed_all (ONE network call)
        ─► write_files ─► resymbol ─► graph_passes ─► prune_orphans
```

- **Global batching** is the load-bearing shape: chunk everything first, embed
  once. Per-file embedding was ~2 sequential requests per file — measured 110
  requests / 28.5 s vs 4 requests / 0.9 s on the same corpus. An embed failure
  aborts *before* any row of the pass is written.
- **Discovery**: universal excludes (incl. `Pods`, `Carthage`, `.gradle`,
  `third_party` — one React Native project contributed 17 864 vendored
  headers), the repo's own ignores, and `git check-ignore` driven in **bytes**
  (text-mode CRLF mangled the paths on Windows and the filter silently
  excluded nothing). Agent-instruction files (`CLAUDE.md`, `AGENTS.md`) are
  excluded — indexing them feeds a search its own operating rules back as
  documentation. Every skip carries its reason into `scan`.
- **Strategies**: `Strategy` is a structural Protocol (`exts`, `parse`,
  `edge_context`, `edges`); the `Registry` consults injected strategies before
  built-ins, so a caller can *override* a shipped language. `edges()`
  returning `None` means "not examined" — different from `[]`, and only the
  second replaces stored rows.
- **Edges** (`edges/`): Python resolves imports (relative levels, submodule
  bindings, **re-exports** — `from ..storage import PIN_KIND` files against
  the *defining* module, not the `__init__`), calls only through resolved
  imports (bare-name matching mints phantom edges), and repo-wide **attribute
  bindings** (`self.x = ImportedClass()` in one file resolves
  `session.x.method()` in another — kept only when the name binds to exactly
  one file). TypeScript resolves all six spellings of a relative specifier,
  including `./thing.js → ./thing.ts` (ESM writes the compiled extension).
  **Pins** (`pins.py`) are language-agnostic: a test naming ≥3 symbols that
  exactly one non-test file declares *pins* that file — the lane that finally
  connected `helpers_test.rb` to `base.rb` on repositories with zero import
  edges.
- **Schema markers** (`EDGE_SCHEMA`, `PIN_SCHEMA`, `SYMBOL_SCHEMA`): derived
  data re-extracts on engine upgrade without re-embedding a chunk; each marker
  is stamped only after something was actually examined, and the pin pass uses
  additive writes (`replace_edges` would erase the import edges the extractor
  just wrote).
- **`build_index`** refuses an empty result by *naming what it saw and what it
  reads* (`NothingToIndex`) — "0 chunks · 0 edges" reported as success once
  cost somebody an afternoon — and refuses to index a path that isn't a
  directory (a typo used to create an empty index beside itself).

### `search/` — the deterministic engine

```
score_chunks:  embed query (1 call) ─► require_same_space ─► QueryContext
               ─► BASE  DenseFileFusion   chunk cosine + 0.5 · file cosine,
                                          both mapped [-1,1] → [0,1]
               ─► LANES TestPenalty ─► LexicalBoost        (order load-bearing)
bundle:        rank_files (STABLE sort) ─► tiers ─► floors (append-only)
               ─► anchors ─► pins ─► evidence band
```

- **`params.RetrievalParams`** — every knob in one frozen dataclass; every
  default is an experiment result with its provenance in the comment
  (`file_fusion_w = 0.5`, `graph_extras = 7`, `anchor_df_cap = 10`, …).
  Variants via `dataclasses.replace()`, never module-global mutation.
- **`TestPenalty` scales the *signal*, not the score.** Fusion's offset means
  a zero-cosine chunk already sits at `neutral_score() = 0.75`; multiplying
  the raw score removed half the dynamic range and delivered the
  best-matching chunk in a repository at #115. It also **stands down** when
  `wants_tests(query)` — a down-weight aimed at the thing the reader asked
  for is an answer being withheld.
- **`intent.py`** — deterministic query reading (`wants_tests`, `is_task`),
  no model on the query path, traps pinned ("how does the test runner
  discover tests" is *not* a request for tests; an interrogative opening
  always beats a change verb).
- **Two recall floors** (`bundle/floors.py`), both pure additions: the file
  floor (a top-N *raw-dense* chunk whose file fusion buried gets a slot; tests
  admitted when tests were asked for) and the anchor floor (a rare multi-word
  identifier the query quoted verbatim, capped by document frequency, tests
  and demos excluded from the count). Plus `pins` and the flow lane — a
  bundle can only ever *gain* files.
- **Determinism defended in three places**: stable argsort on ties, neighbour
  ordering with a total tie-break (a set's iteration order changed the bundle
  per process), and a test that crosses `PYTHONHASHSEED` values in
  subprocesses.
- **Evidence** (`scoring/evidence.py`): the raw top-1 cosine calibrated on two
  corpora into `strong ≥ 0.45 / none < 0.30 / weak between` — the honesty band
  that stops confident prose over vocabulary matches. The fused scale cannot
  say this (zero cosine displays as 0.75). Pre-registered predictions pinned:
  no answerable query lands in "none", no off-topic query in "strong".
- **`widen.py`** — go-to-definition in bulk: expander terms resolve through
  the **symbol table**, never the embedder (measured: embedding the terms
  found none of the ground truth; the symbol table found it exactly). A name
  defined in more than `TOO_AMBIGUOUS = 8` files is vocabulary, not an address.
- **`render/`** — one renderer for every surface; the **map is the default**
  (~2 700 tokens vs ~8 100 with bodies), the header states what the render
  actually carries, and the evidence banner is silent on "strong" — a banner
  on every answer is a banner on none.

### `graph/` — structure, never ranking

- **`build`** — the in-memory `RepoGraph`: structural lanes (`near`/`out`/
  `into`, kinds preserved) + the **semantic lane** (top-3 skeleton-cosine
  twins ≥ 0.80, sparse on purpose). The full cosine matrix is **never
  retained**: at 10 000 files it is 400 MB per map, so the pairs the
  surprises need (≥ `SURPRISE_MIN`) are extracted block-wise while the
  cosines briefly exist and travel on the graph as `twins`. Served views go
  through `warm.warm_graph`, cached per index-file stat, so the studio's
  Graph tab stops paying a full rebuild per click.
- **`node`/`render`** — one file's place, and the surface `megabrain_node`
  serves: both edge directions with the kind of each (`import` vs `call`, one
  row per FILE with its kinds joined — the same rule the map's links use,
  because a file that both imports and calls is ONE dependant and a doubled
  count argues against a safe change), the cluster, the semantic twins, and
  the declared symbols with real spans. It quotes no code, for `grep`'s
  reason. Term resolution is a ladder — exact path, filename tail, then
  MEANING — and the MCP tool passes `guess=False` to stop before the last
  rung: a parameter called `file` that silently returns the *nearest* file
  reads as an answer and sends the agent to edit the wrong one. Every other
  shape of the render was forced by a real repository (fastapi, rails): pins
  are split from dependants (a test fixing behaviour is not code that
  breaks — it inflated `routing.py` to 96), source leads tests and examples
  and the file's own package leads the source (twelve `docs_src/` tutorials
  outranked the four modules that build on it), the outline is capped far
  below the edge lists because it is the ONE part a plain `Read` supplies,
  and — the correctness one — a language whose edges are unknown renders
  **`not extracted`** rather than `none`: a Ruby file another file *requires*
  read as `imported by: none`, which this tool's own description calls dead
  code. `NodeView.edges_known` carries that, and it asks TWO questions
  (`graph/capability.py`): does the engine extract this language, **and does
  this index already hold edges for it** — rails carries 3 094 Ruby edges an
  older engine wrote, so asking only the registry made one file list eleven
  imports while its sibling claimed the language had never been read.
  Strategies declare `extracts_edges` as an OPTIONAL attribute (read with
  `getattr`), so no existing or forge-generated strategy had to change.
  The outline ranks behaviour over bindings for the same reason express's
  `lib/response.js` led with fifteen `const x = require(…)` rows.
- **`clusters/`** — label propagation with `hub_damping = 1/log2(1+d)`
  (measured on a 1 210-file corpus: undamped, 97.5 % of files collapsed into
  one community), semantic ties at half a structural vote (`SEM_WEIGHT =
  0.5`), model-named labels cached under the graph's fingerprint and fail-open
  to "Community N". **Surprises** need three legs: similar (≥ 0.85), no edge,
  different communities — and the genuinely reportable ones are *anchored*
  twins (a free-floating one merges into its lookalike's community and is
  correctly excluded).
- **`routes/`** — Dijkstra with **tolls**: plumbing by name (`__init__.py`,
  test files), hubs by degree above a floored p90 (scaled, not flat),
  semantic edges costlier than structural (a cosine is an opinion, an import
  is a fact), endpoints exempt. `story.py` tells it truthfully: carrier
  symbols per hop with real use/definition snippets, call-flow reorientation
  (declared, never silent, never on a mixed route), and a route through a
  shared callee reported as a **meeting** (`a → M ← b`) with its kind.
- **`symbols/`** — go-to-definition (`links`, `uses`, `locals` — the two
  binding forms that are already an answer: `x = Cls()` and `with Cls() as
  x`), AST-verified use sites (a variable receiver is *inferred*, never
  *verified*), and the uniqueness rule everywhere: a jump that could land
  anywhere is worse than no jump.

---

## 7. L4 — the model lanes

### `providers/chat/` — one Protocol, a registry, two backends

`ChatProvider`: `available()` (cheap, no request), `chat_text`, `stream_chat`,
`agent_stream: … | None` (capability as an attribute, not a subclass check).
**`resolve(model=…, timeout=…, provider=…)` is the one place any lane gets a
backend** — constructing one by name at a call site is the retired bug where
`MEGABRAIN_CHAT_PROVIDER=claude` switched the narrator while the judge kept
billing OpenRouter, silently, because every lane is fail-open. The repo's
committed `models.provider` beats the env var; the env var beats the default.

- **`OpenAICompatible`** — any `/chat/completions` endpoint through the shared
  retry policy. `_frames.py` handles the four silent traps: keep-alive
  comments, fragmented tool calls (accumulated per index), errors inside a
  200 stream (raised — or an outage gets quoted as the model's words), and
  streams ending without `[DONE]`. The `api_key` parameter is genuinely
  three-state: omitted reads the environment, explicit `None` means no key.
- **`ClaudeProvider`** — the Claude Agent SDK driving the bundled Claude Code
  binary. Async SDK from a sync engine via **one background daemon thread
  with one loop** (`_claude_sdk.py` — `asyncio.run` raises under the HTTP
  transport's running loop); a hard wall-clock timeout cancels the future (a
  stalled CLI is otherwise a leaked subprocess per call). The binary is an
  *agent* runtime: every built-in tool is denied and the preamble says so, or
  it spends the turn grepping the repo instead of narrating. `is_error` is
  the refusal flag, not the SDK's `subtype` (observed: a refused run arrives
  as `subtype='success'`). Opt-in only — a backend that takes over because a
  package is importable moves measured numbers with nothing in the output
  saying which lane produced them.

### `enrich/` — `Bundle → Bundle`, fail-open, opt-in

- **`rerank`** — full chunk bodies in **parallel batches of 8** (one
  29-candidate call missed 3/18 targets that batches kept; serially the lane
  cost 16 s), cards carrying the file's *outline* beyond the span (the judge
  once correctly dropped the file defining the routing DSL, judging by the
  only evidence it was shown), verdicts merged round-robin, all-or-nothing
  across batches (a partial verdict is a ranking from half the evidence).
  Unpicked entries are **moved to the tail, never deleted**, and the verdict
  travels on the bundle — "judged and rejected everything" and "the lane
  never ran" are different answers, and the difference is the best signal in
  a weak-evidence run.
- **`expand`** — a model names *identifiers* (never files — allowed to, it
  hallucinated `test/main_test.rb`), echoes of the query are dropped in code
  (`_echo.py` — an instruction the model can ignore is not a guarantee), the
  symbol table resolves, and the loop runs **until a round adds nothing**
  (bounded, `MAX_ROUNDS = 3`). CORE is shown to the namer too — a lane whose
  job is judging what is *missing* must see what was found. The terms travel
  on the bundle (`expanded`) so a reader knows which files answered a model's
  word rather than their question.

### `ask/` — the walkthrough

```
retrieve ─► converse loop (open_file, ≤5 rounds) ─► stream-splice
        ─► checks (callees · pinned · grounded · surface · prune) ─► rescue
        ─► cache flow
```

- **`citing/`** is rule 5 as a package. Two citation grammars share bracket
  syntax — `[[k:lo-hi]]` by chunk index, `[[path:lo-hi]]` by file — told
  apart by `[./]` in the reference. The splice deletes model-written fences;
  point citations widen to a window (one naked line explains nothing);
  oversized citations narrow to `SPLICE_CAP`; a repeated range becomes a
  back-reference; decorators above a cited `def` are pulled in; elision cuts
  from the **middle** (the tail carries the `end` an `insert_after` depends
  on); `repair` sends back *only* the broken fragments (a second narration
  replaces prose the reader is already reading), and the final `drop_unresolved`
  deletes any bracket no splicer accepted — litter reads as a bug.
- **`stream.Splicer`** holds the undecidable tail (`PARTIAL` — a `[[3:70` cut
  by a delta boundary cannot be unprinted) and drops unterminated fences at
  flush, because `splice` only removes fences that close.
- **`converse/`** (top-level, shared with `grep --why`) — the open_file loop,
  bounded (`MAX_ROUNDS = 5`) and
  fail-open. `_toolless` recognises "this backend cannot take tools" (a 4xx
  with known tells, never a 500 — a blanket retry would buy a second outage)
  and retires the field for the whole conversation. `_admits`/`_filled` grant
  exactly one extra round when the answer *confessed* it lacked a body the
  index holds — serving every callee up front was measured (159 bodies on
  sinatra) and rejected.
- **`checks/`** — deterministic post-passes, each born from a measured
  failure: `callees` (the definition of every backticked helper, resolved
  only when unambiguous — a prompt clause was ignored 3/4 times), `pinned`
  (the test 1 800 lines away that the change breaks, via pin edges, gated on
  real assertions so fixtures don't surface), `grounded` (every consecutive
  narrated hop checked against the graph — "delegates to" is a graph fact),
  `surface` (each cited file's import surface as one metadata line — measured
  as three wasted Reads per session), `prune` (a section whose every quote is
  a back-reference is deleted whole).
- **`agents/`** — the multi-question fan-out: parallel sub-agents, each
  spliced (invariant 5 one level down), a hung member dies alone on
  `AGENT_TIMEOUT`, a failed one is dropped and the rest survive.

### `flows/` — walkthroughs as a cache

Two vectors per flow from one embedding call: **attach** (question + prose,
chrome stripped) and **serve** (question alone — a long walkthrough must not
dilute an identical question's score). Serving is additionally gated by
`covers()` — an **asymmetric** containment check cosine cannot make: a
compound question *contains* a cached one at cosine ~1.0 and would be served
half an answer. Flows are pinned to the sha of every file they cited and die
with them at index time; near-duplicate questions replace rather than
accumulate. `strip_chrome()` removes block headers before a flow is shown to
a model — shown the format, the model imitates it and the splicer has nothing
left to replace.

### `forge/` — strategies the machine writes or measures

The one place a model writes CODE, and it happens exactly once, at forge time.
`megabrain forge` censuses the extensions nothing can index (`detect` — no
model), has the repo's chat backend write a *parsing* strategy for them — in
v3 the model writes `parse -> Parsed` and the engine's `Chunker` owns the
partition, a strictly smaller trust surface than v2's whole-chunker codegen —
and accepts it only when the ORACLE passes on every matching file: partition
clean, no raising parser, line-accurate symbols; failures feed a ≤3-round
repair loop. The vetted source installs to `.megabrain/strategies/<ext>.py`
with its sha recorded in the user-owned trust store (`indexing/trust.py`) —
`index_repo` then loads it on every run, a clone's unvetted file loads as
nothing, and an edit after approval silently revokes the trust. `exec` of
vetted code is the package's accepted risk, and it is stated, gated and
logged rather than hidden.

Specialization — re-chunking a file the engine already covers — gets a second,
EMPIRICAL gate (`ab_gate`, no model): neutral probe spans from the file itself,
champion-vs-challenger over throwaway indexed copies, rank-aware IoU + hit@k,
a granularity floor that rejects micro-chunking before any indexing, and
install only on a measured WIN over the lit-2000 baseline (`budget` is data
`chunker_for` honours, which is what made that baseline three lines). The
model-written specialization path was removed in v2 after losing to that free
recipe on four repos — the port keeps the verdict.

### `grep/` — the edit surface

Deterministic lanes over the index (~50 ms, no model): the task's identifiers
matched literally and resolved to the **symbols containing them** (`mentions`
— completeness is computed, not requested of a model; markdown headings are
excluded, or one changelog contributes 29 rows spanning 1 630 lines each), one
hop into what those sites *reference* (`referenced` — the TypedDict in another
file that no literal search reaches, followed only when unambiguous, never
twice), and spread control (`spread` — a one-word name the index *declares* is
chased while a container name is vocabulary; test suites are sampled, never
pasted whole and never zeroed out). `--why` adds exactly one model call whose
output is pipe-shaped rows the engine re-numbers from the symbol table
(`sites` — the model names `Choice.get_metavar`, the index answers L415-430;
it cannot be off by one, and a qualified name beats the base class).

---

## 8. L5 — transports and the studio

- **CLI** — one module per command registering its own flags (`_COMMANDS` in
  `main.py` is the only list); the error taxonomy maps to exit codes
  (0 / 1 engine / 2 usage / 130 interrupt). Deltas stream to stdout, the
  retrieval trace to stderr, so `> answer.md` stays clean. `ui` carries
  `studio` as an alias (published READMEs keep working).
- **MCP** — five tools (`grep`, `ask`, `search`, `node`, `index`), JSON-RPC
  over stdio, schemas **generated** from `contracts/tools/`, `tools/list`
  answerable without importing numpy (pinned by a subprocess test),
  notifications never answered, malformed lines skipped rather than fatal.
  `ask` is buffered — MCP is request/response and a partial stream is a
  half-written walkthrough with no way back.
- **HTTP** — threaded stdlib server, no framework, no async twin of the
  engine. Routes are pure `Request → Reply` functions; `security.Guard`
  enforces token / read-only (`WRITING_PATHS` listed, not inferred) / a
  sliding-window rate limit whose caller map is swept (departed callers are
  forgotten after a window — an attacker must not be able to grow it) and
  whose caller identity can be the first `X-Forwarded-For` hop behind a
  proxy the operator declared (`--trust-proxy`; off by default, because on
  a directly-exposed box the header mints identities); `build_server`
  **refuses** a non-loopback bind
  without a token — indexing is a write endpoint that reads any path the
  process can. SSE frames are single-line JSON terminated by the blank line
  (the whole protocol), chunked and flushed per frame; HEAD is answered
  (monitors send it and the stdlib default is a 501).
- **Studio** (`studio/` → built into `transports/http/ui/`) — a TypeScript
  workspace (esbuild, zero runtime deps) typed against the same `contracts/`.
  Three tabs: **Ask** (retrieval trace *before* the model says anything — the
  deterministic answer is already complete), **Search** (CORE cards closed by
  default + the RELATED map), **Graph** (one bubble per community at the
  overview — the answer to the hairball — click into files, `a → b` routes
  with step-by-step playback through real code, arrowheads carrying the true
  call direction). Plus a read-only navigator and a census-first add-repo
  flow. The built bundle **is committed** so `pip install` serves the UI
  without node; a CI job rebuilds and fails on a non-empty diff.
- **install** — MCP registration for six assistants: JSON hosts merged
  surgically (other servers and unrelated keys survive; a stale megabrain
  entry is replaced, not merged into), the TOML host edited by section
  replacement with comments preserved, broken configs reported rather than
  overwritten. The shared `~/.megabrain/registry.json` is **co-owned with
  v2**: both shapes read, foreign metadata survives writes, dead entries are
  hidden but never deleted — a shared file is nobody's to garbage-collect —
  and every read-modify-write holds an OS lock (`usecases/_lockfile.py`), so
  two concurrent `index` runs cannot interleave and drop an entry.

---

## 9. The gates

| gate | what it holds |
|---|---|
| `./scripts/lint` | ruff + mypy strict + pyright strict + the architecture suite |
| `./scripts/test` | the full offline suite (~1 500 tests — no key, no network, no private corpus) |
| golden (`evals/harness/gate.py`) | `R@1 ≥ 0.86 · bundle_full ≥ 0.90 · p50 < 1 s` against the corpus named by `MEGABRAIN_GOLDEN` + `MEGABRAIN_GOLDEN_REPO`; current numbers: **R@1 0.91 · bundle_full 1.00 · p50 ~10 ms** |
| CI | 3 OS × 4 Python + lint + build + studio-bundle freshness; `release.yml` calls `ci.yml` via `workflow_call` so a tagged commit cannot publish ungated, plus a tag↔`__version__` guard |

The standing rule for any change touching `search/`, `chunkers/` or
`providers/embeddings/`: re-run the golden gate and put the three numbers in
the commit message — not "still passes", the numbers.

---

## 10. Known deliberate gaps

Recorded so absence reads as a decision, not an accident:

- **Issue mode** (v2's long-query lane: BM25 entity-IDs + traceback pins) is
  not yet ported. It doesn't fire on the golden set — which is why parity
  holds without it — and it lands as one more `Lane` beside `TestPenalty`.
- **ANN indexing** is deferred until a corpus demands it.
- The golden corpus is **private**; the harness is committed. External
  validity via a public benchmark is roadmap, not architecture.

For the audit findings, the design debts and the road to 10/10, see
[REFACTOR.md](REFACTOR.md).
