# megabrain — Architecture

> Code-intelligence engine. One call returns all the code related to a question,
> explained like a senior engineer with the real code spliced in. Built to replace
> minutes of agent file-crawling with one grounded answer.

> **Verified against `src/megabrain/` on 2026-07-27.** The sections that described
> packages this branch does not have — `forge/`, `atlas/`, `brief`/`study`, issue
> mode, ask's multi-agent v2 — were removed rather than annotated: a document that
> warns you which of its own paragraphs are lies is a document nobody can use.
> Anything below names a module that exists.

Every load-bearing choice below is locked by experimental data (golden-set gates,
model bakeoffs — see §8). The five hard rules:

1. **No LLM in the retrieval path** — LLM pruning was tested four ways and every
   variant cost completeness or added 1–2 s for no recall gain. Query-time LLM calls
   live *above* retrieval and all fail open: `ask` (the post-retrieval narrator) and
   the optional `enrich/` lanes (`rerank.py` for order, `expand.py` for recall).
   Exactly one model call happens outside a query — `graph/clusters/labels.py` names
   the graph's communities, cached by a fingerprint of the graph — and it cannot reach
   retrieval either. The rule is **enforced by a test that walks imports**: nothing
   under `search/` or `grep/` may import `providers.chat` or `enrich/`. The two verb
   modules (`search/search.py`, `grep/grep.py`) are exempt by name, because composing
   an opt-in lane the caller asked for is their job — the LANES underneath, which are
   where the milliseconds live and what answers when nobody opts in, are fenced.
2. **Completeness beats ordering** — the bundle is tuned so golden `bundle_full`
   recall is **1.00**. A change that lowers it is not merged. Noise is handled by
   *render structure* (§3.3), never by dropping files.
3. **The graph never ranks** — import/call edges supply candidates and map
   annotations only. PageRank-as-ranking was rejected (Acc@1 0.91 → 0.73).
4. **Chunks are a line partition** — every file's chunks cover every line exactly
   once, no gaps, no overlaps (`validate_partition` must stay clean).
5. **`ask` shows real code only** — the LLM cites spans; the engine splices verbatim
   code from disk. The model can never emit (hallucinate) code.

---

## 1. The pipeline at a glance

```
                 INDEX TIME (once per repo, incremental after)
  repo files ──► chunkers (cAST) ──► embed (OpenRouter/local) ──► SQLite (.megabrain/db.sqlite)
                     │                                        chunks · vectors · symbols
                     ├─ symbols (defs/classes/consts)         file skeletons · edges
                     ├─ file skeleton (signatures)            edges · pins
                     └─ import/call graph edges (py · ts/js)

                 QUERY TIME (per question — retrieval itself never calls a model)
  question ──► retrieve (no LLM, ~10–200 ms) ──┬─► [search] the bundle, as a map
               dense + file-fusion + graph     ├─► [grep]   WHERE TO EDIT, no model
                                               └─► [ask]    narrate (1 chat call),
                                                            splicing verbatim code
```

Entry points share one retrieval core: CLI (`megabrain …`), MCP stdio
(`megabrain_ask` · `megabrain_grep` · `megabrain_search` · `megabrain_index` — §5.1), HTTP
(`megabrain studio`, which also serves the studio UI), and the Python API
(`megabrain.search/…`, lazy imports, `py.typed`).

| command | LLM? | latency | use |
|---------|------|---------|-----|
| `search` | no | ~10–200 ms | complete bundle: CORE full code + RELATED map (`--full` for RELATED bodies) |
| `ask`   | 1 chat call | ~6–25 s | narrated walkthrough, verbatim code spliced at each citation |
| `get` | no | <10 ms | one file or symbol |

---

## 2. Index time

### 2.1 Chunkers (`megabrain/chunkers/`)

All chunking sits behind one contract (`chunkers/units.py`): `chunk_file(relpath,
source) -> FileResult` — chunks + symbols + skeleton, **partition-guaranteed**.

Split-then-merge over the AST (the cAST recipe, arXiv 2506.15655): walk top-level
nodes (comment/blank gaps attach to the following unit), **merge** small units up to
a budget of **4000 non-whitespace chars**, **split** oversized ones (big class →
class-header + per-method chunks; big function → `part k/n` blocks; unsplittable
giants → line windows). Every chunk carries a **breadcrumb**
(`repo > path > class Sig > def method(sig)`) that is prepended to the embedded text
(contextual retrieval).

- `python.py` — stdlib `ast`.
- `treesitter/` — the same algorithm parameterized by a **`LangSpec`** (grammar,
  def node types, name/body fields, export unwrap): TS/TSX/JS/JSX, Ruby, Go, Rust,
  PHP, C, C++, Java, C#. Adding a language = one spec entry in
  `treesitter/specs/` + a module in `chunkers/languages/` (13–18 lines) +
  `pip install tree_sitter_<lang>` — it auto-activates when the grammar imports, so a
  missing wheel costs that language and nothing else.
- `php.py` — **shape-routed PHP**: modern (namespaced/PSR) files keep the generic
  chunker; legacy-2000s procedural/mixed-HTML files take a section chunker
  (standalone defs with their doc-banner attached, `//----` banners as headings,
  HTML islands, QMD scored cuts).
- `markdown.py` — no-LLM doc chunker: score candidate cut lines (H1=100…H6=50,
  code-fence boundary=80, paragraph=20) and cut at the best score near the budget,
  so chunks are heading-aligned and never split mid-section. Headings become
  symbols; the outline is the skeleton.

**Custom strategies (public extension point):** the registry contract is the
`Strategy` **Protocol** — an object of the right shape, no import and no inheritance;
`index_repo(root, strategies=[MyStrategy()])` injects caller strategies ahead of the
built-ins — claim a new content type (`.sql`,
`.proto`, `.ipynb`…) or override an existing one without forking. Partition is the
only hard requirement. Runnable demo: the megabrain-examples repo.

### 2.2 Two embedded granularities

Embeddings go through any OpenAI-compatible `/embeddings` endpoint — OpenRouter by
default (model `perplexity/pplx-embed-v1-0.6b`, 1024-d), or a local server
(Ollama/LM Studio/vLLM) via `MEGABRAIN_EMBED_BASE_URL` (keyless on localhost).
Wire detail: int8-base64 **unnormalized** vectors are decoded and L2-normalized
(float arrays handled too). A content-addressed disk cache (atomic writes) makes
re-indexing near-identical checkouts almost free; changing the embed model
auto-triggers a full re-embed on the next `index` so vectors never silently mismatch.

- **Chunk vectors** — breadcrumb + code of each chunk.
- **File skeletons** — per file, signatures + docstrings + module constants embedded
  as one vector: the file-level relevance signal for the fusion in §3.1.

### 2.3 Symbols & graph

- **Symbol table** — every def/class/method/const with qualified name, kind, line
  range, signature, doc first-line. Powers outlines, the entity-ID lexical lane and
  `get --symbol`. Two node shapes are declarations only because a real repository
  said so: a CommonJS `res.send = function () {}` (`LangSpec.assign_defs` — half of
  npm's API) and a mocha/jest `it('…', fn)` (`group_calls`/`case_calls`), which is
  what took express from 3.9 to 12.3 symbols per file. A `describe` is recursed into
  and never recorded: it spans the file, and the lanes keep the symbol no other
  symbol contains, so recording it would swallow every case inside it.
- **`SYMBOL_SCHEMA`** (`indexing/passes/resymbol.py`) — a chunker that learns to see a new
  declaration changes nothing for an already-indexed repo, since the indexer revisits
  a file only when its bytes change. Bumping the marker re-extracts the symbols of
  unchanged files on the next plain `index`, with no embedding calls (measured: seven
  repos, +2 000 symbols, `changed=0`). Symbols only — a change to where a file may be
  CUT still needs `--force`, because those rows carry vectors.
- **Import/call graph** (`indexing/edges/`) — Python: `from pkg.x import Y` + call sites to
  unique defs. TS/JS: relative imports incl. `export * from`, dynamic `import()`,
  side-effect imports. PHP: `use` statements resolved against a namespace+declaration
  FQCN index (PSR-4-agnostic). Edges feed **candidates and annotations only** (rule 3).

### 2.4 Storage, incrementality, freshness (`storage/store.py`, `indexing/indexer.py`)

One SQLite file per repo at `<repo>/.megabrain/db.sqlite` (`chunks`, `files`,
`symbols`, `edges`, `meta`). Indexing is incremental by SHA-256; orphans are pruned
(incoming edges drop only then — re-index preserves them). Relpaths are **POSIX on
every platform** (`as_posix()`; Windows backslash keys corrupted the index once —
CI's Windows matrix is the regression guard). No daemon, no watcher, and — unlike v2 — **no auto-refresh at query time** (§5.1's
last bullet said so all along while this paragraph claimed the opposite; the code
has no refresh on the `search`/`ask`/`grep` path at all). The consequence is worth
knowing because it is invisible: the line numbers a query returns are the INDEX's,
so your own first edit makes them drift. Measured while an agent worked — the index
held 3 792 lines of a file the disk had grown to 3 820, and citations checked
against the edited file looked misattributed when the splice was in fact exact.
Re-run `megabrain index` after editing, or read the ranges before you change
anything. Vectors
load into one NumPy matrix; brute-force cosine is <2 ms up to ~50 K chunks, so ANN
indexing is deliberately deferred.

## 3. Query time — retrieval (no LLM)

`search/` — scoring in `scoring/`, assembly in `bundle/`, and `search.py` as the verb
that composes them and owns the content policy. `load_state()` (in `state.py`) loads matrices once (servers keep it warm and reload on
db-mtime change); `search_with_state()` runs per query, all vectorized.

### 3.1 Scoring

```
dense_i  = cosine(query, chunk_i)                      # chunk relevance
file_i   = cosine(query, skeleton(file of chunk_i))    # file relevance
fused_i  = dense_i + 0.5 · file_i                      # dual granularity (validated)
fused_i *= 0.85   if chunk_i is in a test file         # soft test down-weight
```

The `+ 0.5 · file` term is the validated core hypothesis: a strong chunk in a weak
file shouldn't outrank a decent chunk in the clearly-relevant file. For short
developer queries (≤25 identifier tokens), small grid-tuned boosts reward exact
filename/symbol token matches.

### 3.2 Bundle assembly + the RELATED render policy

Rank files by best chunk; take top candidates; pull **graph neighbors** of the top
files as extras. **CORE** = files within 3% of the top score → matching chunks in
full + a symbol index of the rest. **RELATED** = every other candidate.

Measured on the golden set (22 queries, 40 verified gold files):

| | bundle_full |
|---|---|
| CORE only | 0.36 |
| CORE + RELATED | **1.00** |

**45% of gold files live in RELATED — it can never be dropped** (and LLM pruning
stays rejected: every variant lost gold files). But by *volume*, RELATED is
~17 files/query at ~5% verified gold, and its inline code bodies were ~16K of a
~22K-token render. So the fix is structural, in the **render only**: the default
answer is a MAP — every file with its **best-match span pointer and symbols**, no
bodies (measured on a real bundle: 2 660 tokens against 8 135 for CORE-with-bodies).
`search --full` (MCP `bodies: true`) restores inline code. The bundle **data** always
carries the best chunk either way, so `ask`, the HTTP API and the studio consume one
shape. Expansion is multi-turn and explicit: `megabrain get <file> [--symbol N]`.

**Content policy — code OR docs, one place (`search/search.py`).** `content="code"`
drops markdown before scoring, `content="docs"` flips the whole bundle to markdown,
and `None` lets them compete — which is the honest default for a question whose shape
nobody has inspected. The retrieval primitives stay neutral; the verb is the only
thing that decides, so CLI, MCP, HTTP and the studio cannot drift apart. `ask`
defaults to code instead, because a walkthrough diluted with prose explains the
documentation rather than the mechanism. Blending is not neutral: once a repo indexes both, a large
README wins prose-shaped questions and buries the code (measured on sinatra —
`README.md` displaced `lib/sinatra/base.rb` from CORE for "how are routes defined
and dispatched?"). There is no blend mode anywhere: `ask --with-docs` claimed to
be one and wasn't — it left both filters off, so the same crowding applied and
the prose simply won (CORE = `[README.md]`, no code). Removed in 0.17.1.

**The judge lane (`enrich/rerank.py`, opt-in, `Bundle → Bundle`).**
Retrieval is recall-safe by design — every candidate file contributes its
best chunk — so files that merely *share vocabulary* with the query (tests, eval
scripts, A/B gates) survive and bloat the output; cosine can't tell
"implements scoring" from "tests scoring". This optional lane fixes exactly that: one
buffered call sees a COMPACT view of the RELATED tier (ids + spans + names + a one-line
hint, no bodies, ~2K tokens) and returns the relevant ids, ordered. The engine then
**reorders its own verbatim chunks** — the model *selects*, it never writes code (the
same anti-hallucination stance as ask's splice).

**It never drops a file.** Unpicked entries move behind the picked ones and stay in the
bundle: the recall floors exist so a bundle can only gain files, a judge that deleted
one would undo that from above, and the reader would never learn what was taken. What
does travel is the verdict — `judge: {kept, of}` — because returning the bundle
byte-identical made "judged and rejected everything" look exactly like "the lane never
ran", and that is the one signal the evidence band cannot compute for itself.

Fail-open in every branch (no provider, timeout, malformed reply, unknown ids → the
deterministic bundle untouched) and **opt-in on every surface**: `search --rerank`,
`megabrain_search rerank: true`, `POST /search {"rerank": true}`, the studio's judge
toggle. The model is `models.rerank` / `MEGABRAIN_RERANK_MODEL` — its own constant, never
the narrator's: three batches through the narration model took 16 s for a JSON array of
integers (§4.1). Its sibling `enrich/expand.py` buys the other axis, RECALL, and only
ever adds.

### 3.3 Flow cache — self-caching workflow retrieval (`flows/`, on by default)

**ON by default, and there is nothing to turn on.** The only opt-out is per call —
`ask(..., cache=False)`, which exists so a measurement can see what the engine does
cold, since the second run would otherwise answer from the first. No CLI subcommand
manages it and no environment variable disables it: a cache whose correctness is
guaranteed by sha rechecks (below) has nothing for a flag to protect against.

Every successful `ask` synthesizes a cross-file WORKFLOW ("VAD detects speech →
`TurnController.on_vad_start` → cancel TTS") that used to be thrown away. It is
now cached in the index and the next related question retrieves the whole flow
at once — validated: a barge-in flow cached from one question was retrieved by a
fully re-worded paraphrase. The hard rules stay intact by construction:

- **Write path (ask time)** — the RENDERED walkthrough (prose + the real code
  blocks) goes into the `flows` table with `{cited file: sha}`, and **two**
  vectors are embedded in ONE call: question + prose (the ATTACH lane) and
  question-only (the SERVE lane — so prose length can never dilute an identical
  question). "Prose" means `strip_code`, which removes fenced code, `[[k]]`
  citations **and the rendered citation headers** (`` **`src/x.py` L58-83** — sym ``).
  That last one is not cosmetic: the stored answer is what a later narrator
  reads as context, and a model shown a worked example of its own OUTPUT format
  imitates it — emitting headers instead of `[[k]]`, so the splicer replaces
  nothing and the answer names real files and line numbers with **no code
  behind them** (observed live: eight such headers, zero code). Near-duplicate
  *questions* (cos > 0.92) replace the old row. Fail-open: a cache error never
  breaks ask.
- **Read path (query time, rule 1 intact)** — pure cosine of the
  ALREADY-computed query vector against the flow matrix, in two lanes:
  - **SERVE** (`qscore` ≥ 0.88 on the question-only vector) → the cached answer
    is returned **verbatim, no LLM, ~0 ms** — but only after two guards. The
    shas of every cited file must still match DISK, *and* the cached question
    must **cover** the query (`flows.covers`): nearly every content word of the
    query has to already appear in it. That second guard exists because cosine
    is **symmetric** while "may I reuse this answer?" is not — a compound
    question that CONTAINS a cached one scores ~1.0 against it, so
    *"How do before and after filters run around a handler, **and how is a route
    defined?**"* was served the cached filters walkthrough alone, silently
    dropping the routing half (reported live on sinatra, where both halves were
    cached separately). New content words mean the caller asked for more than
    the cache holds, so the flow falls through to ATTACH and the narrator
    answers the whole question. Question scaffolding ("how does…", "where
    is…") is stopworded out, so it never decides coverage; a re-ask, a light
    rewording, and a query *narrower* than the cached one all still serve.
  - **ATTACH** (0.62 ≤ score < serve, top 2) → the flow becomes a "KNOWN FLOW"
    bundle section + non-citable context for the narrator, which narrates fresh
    and re-caches. Flows never rank or displace files (rule-3 analog) — their
    source files append to RELATED only when missing, pure additions, so
    bundle_full can only rise.
- **Invalidation (index time)** — `index_repo` prunes any flow whose cited
  files changed sha, so a stale walkthrough cannot outlive the code it
  describes. And `ask` splices real code from disk regardless: a stale flow
  could only mis-prioritize, never fabricate (rule 5 untouched).

**Warming it is just asking.** There is no planner command: the way a cache starts full
is that somebody asks the repo's main workflows once. A repo declares those in
`megabrain.json`'s `queries` (or the legacy `.megabrainqueries`), the studio renders them
as one-click chips (`usecases/starters.py`, whose `source` travels with them: `file` when
the repo declared them, `derived` when the index did, `none` when there is nothing),
and clicking through them on day one leaves every answer cached for everyone. Related:
Knowledge Compression via Question Generation (arxiv 2506.13778).

**Staleness is measured against DISK** (`flows/freshness.py:files_current`, shared with
the serve path), not against the index's stored shas — the index is only as current as the
last `megabrain index`, and a flow whose sources are untouched must stay serveable
regardless. `Store` keeps the index-side comparison too, which is the right question for
the *pruning* path at index time and reported as `stale_flows` in the index summary.

---

## 4. `ask` — narration with verbatim code (`ask/`)

The LLM is a narrator that can only **point**, never paste:

1. Retrieve (§3); flatten CORE chunks + RELATED best-chunks into a numbered
   candidate list. Two content modes: **code-only (default)** and `--docs`
   (docs-only) — they partition the bundle, no overlap and no blend. The mode is applied at RETRIEVAL,
   not just to the candidate list (the `content` filter in `scoring/pipeline.py`,
   fail-open both ways): code-only keeps a doc titled like the query from crowding the code
   out, and docs-only keeps the code from taking the slots — post-filtering a
   mixed bundle capped a docs walkthrough at whatever markdown outranked the
   code. Candidates are capped at 200K chars — one call always fits.
2. **One streamed chat call**: the prompt forbids quoting code and requires
   double-bracket citations — `[[3]]` (whole chunk) or `[[3:705-731]]` (line range;
   an `L` prefix is tolerated because models mirror the prompt's `L1-172` headers).
3. **Splice**: every citation is replaced with the **verbatim block from disk**
   (real file, real line numbers; sub-ranges snap to enclosing symbol edges; repeats
   dedupe to a back-reference). The CLI streams live — prose token by token, each
   citation spliced the moment its line completes.
4. **Fail-open**: no key, no citations, or an API error → the full unfiltered bundle.
   Non-cited candidates are always listed in a footer (the filter is never silent).

### 4.1 Chat providers — one adapter, and one model constant per job

`providers/chat/openai_compat.py` (urllib only) speaks any OpenAI-compatible
`/chat/completions`: OpenRouter, a provider's native API, or a local runtime.
`MEGABRAIN_CHAT_BASE_URL` points it anywhere, and a loopback URL needs no key —
`_local.is_local_url` is why, after a version that refused to run against Ollama for want
of a credential. `router.resolve()` probes a registry in order rather than branching at
call sites, so adding a backend is an adapter plus an entry; today the registry holds one.
`stream_chat(with_tools=True)` accumulates fragmented `delta.tool_calls` for the
function-calling loop in `ask/converse/` and `ask/agents/`.

**Two model constants, not one** (`_models.py`), because the jobs are not the same:
`NARRATOR_MODEL = google/gemini-3.1-flash-lite` reasons about a flow in prose,
`RERANK_MODEL = google/gemini-3.5-flash-lite` emits a short id array. Measured over 20
mined cases × 3 repetitions on identical candidate lists, 3.5-lite prunes one file tighter
every repetition at equal recall and ordering; and bigger is *worse* — reasoning models
return empty (thinking eats the 300-token cap) and plain `gemini-3.5-flash`, five times the
price, failed open at 5.6 s. Sharing one model between the two jobs is what made the judge
take 16 s. A repository overrides either in `megabrain.json`'s `models`, which beats
`MEGABRAIN_ASK_MODEL` / `MEGABRAIN_RERANK_MODEL`, which beat the constants.

**Not ported from v2: the Claude Agent SDK provider.** v2 drove the Claude Code CLI, so a
logged-in subscription narrated on Claude Code credits with no key at all. The
`megabrain[claude]` extra is still declared in pyproject and nothing selects it. Tracked,
not dropped.

**Embeddings never use this switch** — they have their own config and their own key vars,
because the two routinely point at different places (embeddings at a hosted model, chat at
whatever is cheap or local this week) and one shared block cannot express that. A hybrid of
local embeddings and a cloud narrator, or the reverse, is an ordinary configuration.

## 5. Serving surfaces

### 5.1 MCP — four tools, and the reason there are only four

`transports/mcp/` (stdio, no deps): **`megabrain_ask`** (the whole flow, narrated),
**`megabrain_grep`** (where to look for a change — files, symbols, real line ranges, and
NO model by default), **`megabrain_search`** (the map, and the docs), **`megabrain_index`**.
Nothing else — no `get`, and no edit tools.

`grep` is the one addition that earned a slot rather than being a subtraction, and it
earned it by replacing something the host already had: an agent about to edit an indexed
repository was running a chain of literal greps, and the index can answer that in ~50 ms
*including* the site whose text never contains the task's own words. It quotes no code on
purpose — the editor opens the file anyway.

It was briefly five. `megabrain_code` (an edit surface) and `megabrain_replace` (a
transactional batch) were measured across five tasks in three languages against a
grep-only agent, and the numbers were good — 19 tool calls by hand against 6 on a
1 220-file repository. But what CARRIED that was the narrator opening files until it had
the whole flow, and that is now `ask`'s own behaviour. The edit machinery around it kept
being discarded by the readers it was built for: a prepared edit batch was wrong both
times it was measured, four readers found the proposed anchor mode misplaced for a guard,
and applying an edit is work the host's own editor already does.

`ask` therefore runs in the régime that made opening happen: the best eight chunk
bodies plus a MAP of the rest, an instruction to open at the TOP of the prompt, and the
`open_file` loop in `_converse`. Served all thirty bodies instead, the same narrator
opened nothing on four questions — including one that said "open this file". Two
deterministic widenings then run with no model call: `_callees` (the definition of every
helper the prose named — three of four measured readers had been paying a second retrieval
call for exactly this) and `_pinned` (the tests that PIN what was described, found through
the indexer's pin edges — the one that catches a test 1 600 lines from the code it
constrains).

Everything else is a deliberate subtraction. Every tool costs the calling agent context and
a routing decision, and the host it runs in already has Read, Grep and an editor. So the
surface carries only what megabrain alone can do; a tool that fetches one span invites the
agent to re-verify what the render already showed.

Two properties worth knowing:

- **The `inputSchema` is GENERATED from `contracts/tools.py`**, not written beside the
  dispatch. A parameter therefore cannot exist on the wire without existing in the
  dispatch, or the reverse — which is how a tool ends up advertising a flag nobody
  reads. The `Annotated[...]` descriptions are part of the contract: they are the only
  thing a calling agent reads before choosing arguments.
- **`dispatch.py` is a table of three-line handlers.** The behaviour lives in
  `usecases/`, so this layer only maps a name to a use case and picks a renderer —
  which is the whole reason the CLI, MCP and HTTP surfaces cannot drift apart.

**MCP runs buffered**, deliberately: the protocol is request/response, so the consuming
agent reads the final text only and streamed events would be written to nobody.
`megabrain_search`'s `rerank` and `expand` default to **false** for the same reason they do
on the CLI — the deterministic answer is complete on its own, and a caller that wants a
model lane asks for it and accepts the call. Registered by `megabrain install`
(`transports/install/`: a table of six assistants, one module per config format, only ever
writing the `megabrain` key and pinning `sys.executable`) or by hand with
`claude mcp add megabrain -- python3 -m megabrain.transports.mcp`.

**A stale index is never auto-refreshed at query time**, unlike v2's 60 s TTL. `index` is
the one verb that reads disk; everything else answers from the index and *says* when what it
serves is behind disk (`get`'s stale marker, `GET /health?freshness=1`, the studio's banner).
An answer that silently re-indexed was an answer whose latency and cost depended on when you
last edited a file.

### 5.2 HTTP (`transports/http/`)

Stdlib `http.server`, warm state, db-mtime auto-reload. The router is a **table** of
`(method, path) → route`, so adding an endpoint is one entry and a path that exists under
another method answers 405 rather than 404:

```
GET  /health (?freshness=1)  /config  /repos  /project  /scan  /get  /symbols  /graph
POST /search   /ask/stream (SSE)   /index/stream (SSE)
GET  /  and  /ui/*           the studio bundle, the only prefix route
```

Optional Bearer auth (`--token` / `MEGABRAIN_API_TOKEN`) on everything but `/health`,
`/config` and the UI; `--readonly` 403s the mutating routes so a public box cannot be billed
by a visitor; `--rate-limit N` caps requests per minute per caller. `get_code` enforces
repo-root containment (path-traversal hardened). `/repos` merges this server's warm repos
with the machine-global registry, so a repo indexed elsewhere comes back for the studio to
load on click.

**PATH-SCOPE everywhere**: pass a sub-path (`~/repo/src/auth`) or `scope_path`/`path_filter`
and retrieval is confined to files under it; the repo root is auto-detected from
`.megabrain` up the tree. Scoping EXCLUDES everything outside, so a package root is the
right granularity — its `src/` subfolder cuts away the tests that specify it.

---

## 6. Graph — the repo as a knowledge graph (`graph/`)

Where a tool like graphify spins up LLM sub-agents to *extract* relationships, megabrain
already owns them: the AST import/call edges (the `edges` table from §2.3) are the
**structural lane**, and the per-file skeleton embeddings (§2.2) add a **semantic lane**
(cosine — files that talk about the same thing without importing each other). No networkx,
no new store: it reads what indexing already produced (`Store.all_edges()` +
`Store.file_chunks()` were added for it) and runs pure numpy over it.

- **Semantic edges** — skeleton-vector cosine, top-3 twins per file above `SEM_EDGE_MIN
  = 0.80`, capped to keep the graph sparse (`SEM_TOP_K = 3`).
- **Communities** — deterministic weighted **label propagation** (numpy): structural edges
  weight 1.0 per kind, semantic edges `SEM_WEIGHT = 0.5 · cosine`; fixed ascending visit
  order + smallest-label tie-break → byte-stable across runs, renumbered by size. **No
  PageRank:** PageRank-as-*ranking* was rejected by experiment (rule 3, Acc@1 0.91 → 0.73),
  but that verdict is about ranking; communities are STRUCTURE, a different use, and label
  prop is parameter-free.
- **God nodes** — the highest structural-degree files, the repo's core abstractions.
- **Surprises** — pairs with cosine ≥ `SURPRISE_MIN = 0.85`, **no** structural edge, in
  **different** communities: the connection you didn't know was there, scored honestly.
- **Paths** — BFS between two nodes over the combined graph, each hop labelled by what
  carries it (an edge kind, or `semantic 0.87`). Endpoints resolve by **embedding**: a
  concept ("the scoring pipeline") finds its file, not just an exact path match.

The **only** LLM touch is community *labeling* — one buffered call names each community
in 2–4 words, cached in the store's `meta` table under a graph fingerprint (files + edge
counts + thresholds), fail-open to "Community N" (and `--no-labels` / offline skips it
entirely). Everything else is deterministic. `mode=node` splices the file's REAL chunks —
the graph never paraphrases code (rule 5 holds here too).

Surfaces: CLI `megabrain graph [path] [--node F] [--from A --to B] [--code] [--no-labels]
[--json]`, HTTP `GET /graph?mode=map|node|path&node=&source=&target=&repo=`, and the
studio's force-directed canvas (§5). **Not an MCP tool** — the map is a human's reading
aid, and a fifth tool would cost every agent a routing decision for something `ask` and
`grep` already answer in the shape an agent needs. Measured: this repo 122 files / 324
links in ~8 ms; graphify 630 files in ~37 ms.

---

## 7. Layout

The tree mirrors the pipeline — content → index → retrieval → narration →
surfaces — one subpackage per layer (src/ layout, PyPA standard). Loose files
at the package root are only the cross-cutting spine:

Layers are numbered L0–L5 and the dependency arrow only ever points **down**. Two of
them are enforced by executable tests rather than documented: `search/` may not import
`providers.chat` or `enrich/` (rule 1), and only `storage/` may write SQL.

```
src/megabrain/
  L0  _types.py        NotGiven / Omit sentinels — the three-state vocabulary
      _arrays.py       Vector / Matrix / IndexArray (numpy dtypes, kept apart from
                       _types so importing a sentinel never drags numpy in)
      _errors.py       the taxonomy: MegabrainError → code + http_status, dual
                       inheritance for back-compat (IndexNotFound is a ValueError)
      _version.py · _home.py · _models.py (the three default models, one per JOB)
      _config_file.py  reading a JSON file a person edits by hand
      project.py       megabrain.json — what a REPOSITORY decides about itself
                       (ignore · gitignore · queries · models.{narrator,rerank})
      __init__.py      public API: lazy __getattr__ + a TYPE_CHECKING block, so
                       `import megabrain` costs no numpy (pinned by a test)

  L1  contracts/       EVERY cross-boundary payload, TypedDict only, zero logic
                       chunk · bundle · file · graph · node · repo · route · scan ·
                       prune · lanes · install · tools (the MCP inputSchemas' source)

  L2  storage/         PERSISTENCE — the ONLY package allowed to write SQL
        store.py         connection + schema; one table per object
        schema.py        DDL + versioned migrations (chunks · files · symbols ·
                         edges · meta · flows · cards)
        _chunks · _files · _symbols · _graph · _flows · rows.py (the typed rows
                         every table hands back)
        _blobs.py        the untyped sqlite↔numpy boundary
        locate.py        resolve_root + INDEX_FILE — the layout lives in ONE line
      providers/       model APIs — one folder per backend, plus what they share
        _local.py        is this endpoint on this machine? asked by BOTH backends
        http/            attempt.py · retry.py · _urllib.py · _stream.py
        embeddings/      client.py (OpenAI-compatible /embeddings) · cache.py
                         (content-addressed) · _config _send _batching _budget
                         _oversize _wire _width _replies
        chat/            L4 — nothing under search/ may import this
          base.py          ChatProvider Protocol · openai_compat.py · router.py

  L3  chunkers/        CONTENT → CHUNKS behind one partition-guaranteed contract
        cast.py          the ONE split-then-merge engine · units.py the language seam
        model.py         Chunk/Symbol/FileResult + validate_partition (the oracle)
        _cast/           the cAST recipe: _split _merge _balance _spans
                         _breadcrumb _signature — none of them knows the language
        treesitter/      ONE walk, parameterised by a table: chunker.py _langspec
                         _names _nodes _symbols _calls (a mocha `it(…)` is a symbol)
          specs/           core.py · c_family.py · optional.py — the language tables
        languages/       one module per language, 13-18 lines each: python markdown
                         typescript c cpp csharp go java php ruby rust (+_pysymbols)
      indexing/        BUILD the index
        indexer.py       orchestration · discover.py the walk · strategies.py the
                         ext → Strategy registry (OCP) + EDGE_SCHEMA
        passes/          plan → embed → write → resymbol. The ORDER is the design:
                         a network failure in embed aborts before write touches a row
        edges/           python.py · typescript.py · pins.py (test → impl) ·
                         _imports _calls _attrs _reexports _rebuild
        builtin.py       the shipped strategies · _languages.py which ones ship on
        _exclude.py      megabrain.json ignores + the legacy dotfiles
        _gitignore.py    the repo's own .gitignore (on by default, opt-out)
        unsupported.py   the census of files NOTHING can chunk
      search/       ANSWER queries — NO LLM IN HERE (rule 1, enforced by a test)
        search.py        the neutral primitive · params.py every knob, frozen
        state.py         SearchState + load_state (warm matrices)
        paths.py         is_test / is_demo / ident_tokens — path vocabulary
        scoring/         pipeline · lane · lanes (TestPenalty, LexicalBoost) ·
                         _fusion (the BASE: dense + 0.5·file) · _space · context
        bundle/          assemble · _rank · _related · _anchors · floors (the two
                         recall floors) · _pins · widen · _convert
        render/          markdown · _entries · _evidence · _fence · _lang
        intent.py        what SHAPE of question this is — no model, no network
      graph/       THE GRAPH (§6) — candidates + annotations, never ranking
        build.py         RepoGraph + load_graph · node.py · views.py the map
                         weights · semantic · aliases — what an edge WEIGHS
        clusters/        communities · labels · _naming · gods · surprises
                         ← the package's ONLY LLM touch lives here, on purpose
        routes/          paths (BFS) · route · story · carriers · tolls
        symbols/         links · locals · resolve · uses · usesites · source · snips

  L4  enrich/          Bundle → Bundle, opt-in, fail-open to the input
        rerank.py        the judge lane: the model returns IDS, never code
        expand.py        the widener: the model names identifiers, the SYMBOL TABLE
                         resolves them — a name it cannot resolve is dropped
        _batches · _cards · _prompt · _verdict · _terms · _echo
      ask/             NARRATE — the only layer that talks to an LLM at query time
        narrator.py · events.py · stream.py
        prompt/          what the model is HANDED: 8 bodies + a map of the rest.
                         Served all 30, it opened nothing (§5.1)
        converse/        the open_file loop — loop.py tools.py _toolcall _flowctx
                         _missing _filled _admits
        citing/          RULE 5 as a package: the model cites, the ENGINE splices.
                         citations splice _quote _window _elide _codeonly _litter
                         _broken repair _rescue
        checks/          deterministic, no model: grounded pinned callees prune surface
        agents/          fan-out, one sub-narrator per subsystem
        ask.py           the VERB: retrieve → serve from cache or narrate → remember
      grep/            WHERE TO EDIT — its own package, so "it calls no model" is a
                       test and not a promise: grep.py the verb (the opt-in `why`
                       lives HERE, above the lanes) · sites mentions referenced
                       spans idents spread rows words — none of them can call out
      flows/           the cached-walkthrough lane (cache · serve · match · covers ·
                       freshness · chrome)

  L5  usecases/        the verbs that belong to no single feature — get · scan ·
                       repos · freshness · starters · _registry. `ask`, `grep`,
                       `search` and `index` live in THEIR OWN packages, next to the
                       logic they compose, and are re-exported from here so every
                       transport still has one import to reach any verb.
      transports/      SURFACES — thin adapters: args → use-case → render
        cli/            main.py + commands/{index,scan,search,ask,grep,get,
                        graph,studio,install}.py — one per verb, no branch in main
        mcp/            server · protocol · dispatch (a TABLE of 3-line handlers) ·
                        tools (the four) · schema (inputSchema GENERATED from
                        contracts/tools.py) · arguments · answers · __main__
        http/           app · router (a TABLE, never a chain of ifs) · messages
                        (the two records) · replies (the Reply factories) · _target
                        (wire parsing) · _handler · _writer · sse · security
          routes/         query (search · get · symbols) · asking · indexing ·
                          graph · project · meta · scanning · static
studio/                the studio's TypeScript workspace (esbuild → transports/http/ui/)
  src/views/           ask · search · graph · files · adding · progress
```

Not yet ported (deliberate, tracked): `forge/` — chunkers the engine writes for itself, gated by the partition oracle. Nothing else from v2 is pending; what is missing was removed on purpose.

The tree-sitter chunker and its languages ARE ported, contrary to what this note
said until the packages were reorganised: eleven of them live in
`chunkers/languages/`, gated on their grammar being installed.

Runnable examples (programmatic API · custom .sql chunker · chunk heatmap ·
web demo) live in their own repo, `~/megabrain-examples` — they need the engine
installed (`pip install megabrain`).

Public API (lazy, typed): `megabrain.{index_repo, discover, search,
search_with_state, load_state, score_chunks, Store, ChunkMeta, Strategy, Registry,
Chunk, Symbol, FileResult, validate_partition, MegabrainError, IndexNotFound,
EmptyIndex, ModelMismatch, MissingCredential, MissingAPIKey, ProviderError}` — a
lazy `__getattr__` over a name→module map, with a `TYPE_CHECKING` block so checkers
and IDEs still see real symbols, and `__all__` spelled out rather than derived
(a checker cannot follow `[*mapping]`, and the two are pinned to each other by a
test). `import megabrain` loads no numpy — also pinned by a test. The verbs live in
`megabrain.usecases`: `ask · grep · search · build_index · get_code · scan ·
freshness · starters_for · known · remember · resolve_root`.

---

## 8. Evidence (where the numbers live)

- **Golden gate** (30 human-verified queries over a private corpus, maintainer-side):
  R@1 **0.86** · **bundle_full 1.00** · p50 ~10 ms warm. Multi-repo and 134K-line
  scale gates alongside. The offline suite (`python -m pytest`, no network/key) is
  what CI runs on 3.10–3.13 × Linux/macOS/Windows.
- **RELATED analysis** (this doc, §3.2): CORE-only bundle_full 0.36 vs 1.00 with
  RELATED; RELATED ≈ 5% verified gold by count but 45% of all gold files.
- **Embedding bakeoff**: pplx-embed-v1-0.6b beat pplx-4b, codestral-embed,
  openai-3-large and bge-m3 on code recall (`evals/`).
- **Ask-model bakeoff**: qwen3-coder ≈ claude-haiku on citation selection at ~5×
  lower cost (`evals/`).
- **SWE-bench Lite localization** (no training): retrieval-only Acc@1 ≈ 0.52 / @5 ≈
  0.83 — on par with the trained CodeRankEmbed retriever; ask-cited-files Acc@1 ≈
  0.69–0.71, in range of SWE-bench-trained SweRankEmbed-Large.
