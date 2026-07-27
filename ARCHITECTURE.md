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
   the optional judge lane (`enrich/rerank.py`). Two passes run an LLM at **index**
   time instead, each gated by a deterministic oracle that decides whether the output
   `clusters/labels.py` names the graph's communities at index time, cached by a
   fingerprint of the graph. It is the only LLM call outside a query, and it
   cannot reach retrieval.
2. **Completeness beats ordering** — the bundle is tuned so golden `bundle_full`
   recall is **1.00**. A change that lowers it is not merged. Noise is handled by
   *render structure* (§4.3), never by dropping files.
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
                     └─ import/call graph edges (py)

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
  PHP. Adding a language = one LangSpec entry + `pip install tree_sitter_<lang>`
  (auto-activates when the grammar is installed).
- `php.py` — **shape-routed PHP**: modern (namespaced/PSR) files keep the generic
  chunker; legacy-2000s procedural/mixed-HTML files take a section chunker
  (standalone defs with their doc-banner attached, `//----` banners as headings,
  HTML islands, QMD scored cuts).
- `markdown.py` — no-LLM doc chunker: score candidate cut lines (H1=100…H6=50,
  code-fence boundary=80, paragraph=20) and cut at the best score near the budget,
  so chunks are heading-aligned and never split mid-section. Headings become
  symbols; the outline is the skeleton.

**Custom strategies (public extension point):** the registry contract is the
`ChunkStrategy` protocol; `index_repo(root, strategies=[MyStrategy()])` injects
caller strategies ahead of the built-ins — claim a new content type (`.sql`,
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

`search/` (scoring in `scoring/`, assembly in `bundle/`, exposed through
`app.py`'s use-case layer). `load_state()` (in `state.py`) loads matrices once (servers keep it warm and reload on
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

### 3.3 Bundle assembly + the RELATED render policy

Rank files by best chunk; take top candidates; pull **graph neighbors** of the top
files as extras. **CORE** = files within 3% of the top score → matching chunks in
full + a symbol index of the rest. **RELATED** = every other candidate.

Measured on the golden set (22 queries, 40 verified gold files):

| | bundle_full |
|---|---|
| CORE only | 0.36 |
| CORE + RELATED | **1.00** |

**45% of gold files live in RELATED — it can never be dropped** (and LLM pruning
stays rejected: every phase-5 variant lost gold files). But by *volume*, RELATED is
~17 files/query at ~5% verified gold, and its inline code bodies were ~16K of a
~22K-token render. So the fix is structural, in the **render only**: RELATED shows
**file · best-match span pointer · symbols** by default (−65% tokens, 22K → 8K);
`search --full` (MCP `full: true`) restores inline bodies; `--compact` strips all
bodies. The bundle **data** always carries `best_chunk` — ask, serve-api and the
webui consume it unchanged. Expansion is multi-turn: `megabrain get <file>
[--symbol N]`.

**Noise pruning (`prune_search`, no LLM).** The bundle already marks which
chunks are *signal* — a tier-1 chunk that survives the `CHUNK_KEEP_RATIO` cut, or a
related file's best chunk. `prune_search` (CLI `search --prune`, and the ONLY shape
`megabrain_search` returns over MCP) simply **projects that existing selection into a flat list
ranked by relevance** — each `[id] file:Lstart-end · score` with its code, the noise
chunks dropped. No new scoring, no LLM, no token cost: it reuses the same
signal/noise call the full bundle makes, just rendering the signal alone (with
`include_pruned` it also returns the dropped `noise` for a signal-vs-noise diff). It
is the lean read-path answer for a coding agent that wants only the code worth
reading, not a narration; a plain `search` still returns the full CORE+RELATED bundle.

**Content policy — code OR docs, one place (`app.content_filters`).** Every search
verb ranks code and drops markdown before scoring; `docs=true` flips the whole
bundle to markdown. The retrieval primitives stay neutral (both filters default
off) — `app.py` is the only thing that decides, so CLI, MCP, HTTP and the studio
cannot drift apart. Blending is not neutral: once a repo indexes both, a large
README wins prose-shaped questions and buries the code (measured on sinatra —
`README.md` displaced `lib/sinatra/base.rb` from CORE for "how are routes defined
and dispatched?"). There is no blend mode anywhere: `ask --with-docs` claimed to
be one and wasn't — it left both filters off, so the same crowding applied and
the prose simply won (CORE = `[README.md]`, no code). Removed in 0.17.1.

**LLM rerank (`search/rerank.py`, the `llm_rerank` lane, layered ON the prune).**
The deterministic prune is recall-safe by design — every bundle file contributes its
best chunk — so files that merely *share vocabulary* with the query (tests, eval
scripts, A/B gates) survive as "signal" and bloat the output; cosine can't tell
"implements scoring" from "tests scoring". This optional lane fixes exactly that: one
buffered LLM call sees a COMPACT view of the pruned candidates (ids + spans + names +
a one-line hint, no bodies, ~2K tokens) and returns only the relevant ids, ordered.
The engine then keeps/reorders its **own verbatim chunks** and moves the dropped ones
to `noise` — the model *selects*, it never writes code (the same anti-hallucination
stance as ask's splice). It does **not** touch the deterministic scoring or ranking
(rule 1's core stays LLM-free); it is a post-retrieval selector, fail-open in every
branch (no key, timeout, malformed reply, unknown ids → the deterministic result is
returned untouched — the LLM is an optimization, never a dependency). Opt-in on the
CLI (`search --rerank`, which implies `--prune`); **default-on over MCP**
(`megabrain_search rerank: true`) and via `GET /prune?rerank=1`. Model:
`MEGABRAIN_RERANK_MODEL`, falling back to `ask_model()`. Measured on this repo's
scoring query: 21 signal chunks → 6.

### 3.4 Flow cache — self-caching workflow retrieval (`flows/`, on by default)

**ON by default (since 0.11)** — a repo opts out with `megabrain flows
--disable` (persisted in the index meta; meta absent = on, so existing indexes
flip on without a re-index), and env `MEGABRAIN_FLOW_CACHE=0` is the global
kill that beats even a per-repo enable. When off, `load_state` skips flows
entirely and `search`/`ask` are byte-for-byte the prior behavior at zero cost.
When on — the default:

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

**Warmup (explicit, costs LLM):** `megabrain index --warm-flows N` / `flows --warm N` — right
after the first index, an index-time LLM planner reads the graph's hub files (top
edge-degree) + their doclines and writes N research questions covering the main
workflows, then runs one `ask` each, so the cache starts full on day one instead
of building up lazily. Fail-open to deterministic template questions if the
planner errors. CLI `megabrain flows <repo> [--enable|--disable|--warm N|--clear]`
· kill switch `MEGABRAIN_FLOW_CACHE=0`. Related: Knowledge Compression via
Question Generation (arxiv 2506.13778).

**Inspection & onboarding:** the cache is listable everywhere — CLI
`megabrain flows`, MCP `megabrain_flows` (`action=list|get|delete|warm|
refresh|enable|disable`; `get` hands an agent a cached walkthrough for free —
no LLM, no retrieval), HTTP `GET /flows` (list) / `GET /flow?id=` (the stored
walkthrough) / `POST /flows/delete`, and the studio's **Flows tab** (list +
viewer, cited files openable in the navigator, stale marked). All of them go
through the same `app.flows_list/flow_get/flow_delete` use-cases, so no
surface can drift. **Staleness is measured against DISK** (`files_current`,
shared with the serve path), not the index's shas — the index may lag disk by
the 60 s TTL, and a flow whose sources are untouched stays serveable through
that window. `Store.stale_flows()` keeps the index comparison, which is the
right question for the *pruning* path. The Ask
surfaces show the cache working: a verbatim serve is bannered
"⚡ served from flow cache"; attached flows show as "known flows" chips (the
`search` stream event carries them). A repo can commit **starter queries**
at `<root>/.megabrainqueries` (one per line, `#` comments; `GET /queries`):
the studio renders them as one-click chips in Ask with an explicit **Warm
all** button — the newcomer flow: open the repo, click through the starters,
see the main workflows, and leave them cached for everyone.

---

## 4. `ask` — narration with verbatim code (`ask/`)

The LLM is a narrator that can only **point**, never paste:

1. Retrieve (§3); flatten CORE chunks + RELATED best-chunks into a numbered
   candidate list. Two content modes: **code-only (default)** and `--docs`
   (docs-only) — they partition the bundle, no overlap and no blend. The mode is applied at RETRIEVAL,
   not just to the candidate list (`scoring.filter_doc_chunks`, fail-open both
   ways): code-only keeps a doc titled like the query from crowding the code
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

### 4.1 Chat providers — Claude Code credits or OpenRouter

Chat routing (`providers.chat_provider()`) is **auto**: `claude` when
`claude_agent_sdk` is importable, else `openrouter`; pin with
`MEGABRAIN_CHAT_PROVIDER`. The narrator model per provider via `MEGABRAIN_ASK_MODEL` (defaults: `haiku` on
claude, `qwen/qwen3-coder` on
OpenRouter — a bakeoff found qwen on par with Haiku on citation selection at ~5×
lower cost, since retrieval already guarantees completeness).

- **`claude`** — NOT PORTED to this branch. v2 drove the Claude Code CLI through
  the Agent SDK, so a logged-in subscription narrated on Claude Code credits with
  no key at all. `providers/chat/` here holds `openai_compat` and the router;
  `MEGABRAIN_CHAT_PROVIDER=claude` has nothing to select. Tracked, not dropped —
  the extra `megabrain[claude]` is still declared in pyproject.

- **`openrouter`** (`providers/chat/openai_compat.py`, urllib-only) — any OpenAI-compatible endpoint;
  `MEGABRAIN_CHAT_BASE_URL` points it at native APIs or local servers. For ask v2,
  `stream_chat(with_tools=True)` also accumulates fragmented `delta.tool_calls`
  and the loop runs in `ask/agents/`.

**Embeddings never use this switch** — Anthropic has no embeddings API, so
index/query always need OpenRouter or a local embed endpoint. The two lanes are
independent by design (hybrid local-embed + Claude-narrate works).

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

`ask` therefore runs in the régime that made opening happen (§4.2): the best eight chunk
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

- **MCP** (`transports/mcp/`, stdio, no deps): `megabrain_ask` (`question`,
  `scope_path`, `content=code|docs` — MCP is request/response, so it runs buffered:
  the consuming agent reads the final text only, and events would be written to
  nobody), `megabrain_search` (`task`,
  `scope_path`, `content`, `bodies`, `rerank` default **false** — the deterministic
  answer is complete on its own, and a caller that wants the judge lane asks for it
  and accepts the call), `megabrain_index` (`force`). Nothing else: single-file and
  single-symbol fetches are the host's own Read/Grep job. Registered by `megabrain install`
  (`transports/install/`: a table of six assistants, one module per config format,
  only ever writing the `megabrain` key and pinning `sys.executable`) or by hand with
  `claude mcp add megabrain -- python3 -m megabrain.transports.mcp`; a stale index is
  not auto-refreshed at query time, unlike v2.
- **HTTP** (`transports/http/`, stdlib `http.server`, warm state, db-mtime auto-reload):
  `/search` `/docsearch` `/chunks` `/ask` `/ask/stream` (SSE: the ask v2 event
  stream — plan, per-agent deltas/tools, spliced synthesis) `/prune` (`?rerank=1` runs
  the §3.3 LLM rerank over the signal chunks; `?docs=1` the docs-only lane) `/graph` (`?mode=&node=&source=&target=` —
  the §6 knowledge graph) `/get` `/index` (`/index/stream` SSE per-file progress)
  `/repos` (this server's warm repos **merged with the machine-global registry** —
  registered-elsewhere repos come back `loaded: false` so the studio can load them on
  click) `/providers` `/health`. Optional Bearer auth (`--token` / `MEGABRAIN_API_TOKEN`)
  on everything but `/health`; `get_code` enforces repo-root containment (path-traversal
  hardened). `/docsearch` groups are per-deployment config
  (`.megabrain/docsearch.json` or env), not engine knowledge.
- **PATH-SCOPE** everywhere: pass a sub-path (`~/repo/src/auth`) and retrieval is
  confined to files under it; the repo root is auto-detected from `.megabrain` up
  the tree. Multi-repo: comma-separated roots, searched concurrently, merged by
  score.
- **Web demo** (the megabrain-examples repo, stdlib, one port): live file ranking → per-chunk
  heatmap (`chunks_for_file` — span, score, *selected by the real cross-file
  retrieval* flag), native folder picker, doc-mode toggle, and an **Explain** overlay
  that A/Bs the same question on Claude vs OpenRouter with per-stage timings —
  streamed over `/api/ask/stream` (SSE): one card per sub-agent appears at `plan`,
  streams its prose and tool calls live, minimizes on `agent_done`, and the
  synthesis renders below with the real code spliced in.

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

Surfaces: CLI `megabrain graph [path] [--node F] [--path A B] [--no-labels] [--json]`,
MCP `megabrain_graph(repo_path, mode=map|node|path, node?, source?, target?, scope_path?)`,
HTTP `GET /graph?mode=&node=&source=&target=&repo=`, and the studio's force-directed
canvas (§5). Measured: this repo 122 files / 324 links in ~8 ms; graphify 630 files in
~37 ms.

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
                       prune · lanes · install · tools

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
                         recall floors) · _convert
        render/          markdown · _lang
      graph/       THE GRAPH (§6) — candidates + annotations, never ranking
        build.py         RepoGraph + load_graph · node.py · views.py the map
        graph/           weights · semantic · aliases — what an edge WEIGHS
        clusters/        communities · labels · _naming · gods · surprises
                         ← the package's ONLY LLM touch lives here, on purpose
        routes/          paths (BFS) · route · story · carriers · tolls
        symbols/         links · locals · resolve · uses · usesites · source · snips

  L4  enrich/          Bundle → Bundle, opt-in, fail-open to the input
        rerank.py        the judge lane: the model returns IDS, never code
        _batches · _cards · _prompt · _verdict
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
        sites/           WHERE TO EDIT — the lanes behind megabrain_grep, and NO
                         model: sites mentions referenced spans idents spread rows words
      flows/           the cached-walkthrough lane (cache · serve · match · covers ·
                       freshness · chrome)

  L5  usecases/        ONE FILE PER VERB — every transport calls THESE
        get · scan · repos · freshness · starters — the verbs that belong to no
        single feature. `ask`, `grep`, `search` and `index` live in THEIR packages.
        search · ask · get · scan · repos · freshness · _flows · _registry
      transports/      SURFACES — thin adapters: args → use-case → render
        cli/            main.py + commands/{index,scan,search,ask,grep,get,
                        graph,studio,install}.py — one per verb, no branch in main
        mcp/            server · protocol · dispatch (a TABLE of 3-line handlers) ·
                        tools (the three) · schema (inputSchema GENERATED from
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

Public API (lazy, typed): `megabrain.{index_repo, search, render, get_code,
load_state, search_with_state, prune_search, prune_search_root, render_pruned,
Store, ChunkMeta, ChunkStrategy, Chunk, Symbol, FileResult, validate_partition,
MegabrainError, IndexNotFound, EmptyIndex, MissingAPIKey, ProviderError}`; the
walkthrough via `from megabrain.ask import ask, render_ask, stream_ask`.
`prune_search(state, query, path_filter=None, with_text=True,
include_pruned=False)` returns `{query, repo, chunks:[{id, file, start_line,
end_line, kind, name, score, text}], kept, pruned, scanned, ms}` (with
`include_pruned=True`, also `noise:[...]`); `prune_search_root(root, query, …)` is
the one-shot entry.

---

## 8. Evidence (where the numbers live)

- **Golden gate** (30 human-verified queries over a private corpus, maintainer-side):
  R@1 **0.86** · **bundle_full 1.00** · p50 ~10 ms warm. Multi-repo and 134K-line
  scale gates alongside. The offline suite (`python -m pytest`, no network/key) is
  what CI runs on 3.10–3.13 × Linux/macOS/Windows.
- **RELATED analysis** (this doc, §3.3): CORE-only bundle_full 0.36 vs 1.00 with
  RELATED; RELATED ≈ 5% verified gold by count but 45% of all gold files.
- **Embedding bakeoff**: pplx-embed-v1-0.6b beat pplx-4b, codestral-embed,
  openai-3-large and bge-m3 on code recall (`evals/`).
- **Ask-model bakeoff**: qwen3-coder ≈ claude-haiku on citation selection at ~5×
  lower cost (`evals/`).
- **SWE-bench Lite localization** (no training): retrieval-only Acc@1 ≈ 0.52 / @5 ≈
  0.83 — on par with the trained CodeRankEmbed retriever; ask-cited-files Acc@1 ≈
  0.69–0.71, in range of SWE-bench-trained SweRankEmbed-Large.
