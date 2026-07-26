# megabrain — Architecture

> Code-intelligence engine. One call returns all the code related to a question,
> explained like a senior engineer with the real code spliced in. Built to replace
> minutes of agent file-crawling with one grounded answer.

> ⚠️ **This document is being rewritten for v3 and is partly stale.** Accurate as of
> the v3 branch: the hard rules, §1's shape, §4.5 (the atlas) and §7's layout. Still
> describing **v2**, with names and modules that have moved or do not exist yet: the
> `forge` sections (§2.5), the flow-cache narrative (§3.4), `--prune`/`prune_search`
> (§3.3), and the HTTP entry-point bullet in §5. The MCP surface is v3-accurate as of
> phase 13 — four tools, §5.1. Verify against `src/megabrain/` before trusting a name
> in those sections.

Every load-bearing choice below is locked by experimental data (golden-set gates,
model bakeoffs — see §8). The five hard rules:

1. **No LLM in the retrieval path** — LLM pruning was tested four ways and every
   variant cost completeness or added 1–2 s for no recall gain. Query-time LLM calls
   live *above* retrieval and all fail open: `ask` (the post-retrieval narrator) and
   the optional judge lane (`enrich/rerank.py`). Two passes run an LLM at **index**
   time instead, each gated by a deterministic oracle that decides whether the output
   may be stored at all — `forge` (§2.5, the partition oracle) and `study` (§4.5, the
   card oracle). Neither can reach a query.
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
                     ├─ file skeleton (signatures)            cards (study)
                     └─ import/call graph edges (py)

                 STUDY TIME (opt-in: `index --llm` / `study`; ONE chat call per file)
  file skeleton ──► model writes 3-5 sentences ──► ORACLE (no LLM) ──► cards table
                    "what IS this file"           reject → retry → degrade to skeleton

                 QUERY TIME (per question — retrieval itself never calls a model)
  question ──► retrieve (no LLM, ~10–200 ms) ──► bundle ──┬─► [ask]   narrate (1 chat call)
               dense + file-fusion + graph                │          splice verbatim code
                                                          │          into [[k]] cites
                                                          └─► [brief] the SAME file list,
                                                                     re-presented: cards +
                                                                     live graph relations +
                                                                     interfaces (0 calls)
```

Entry points share one retrieval core: CLI (`megabrain …`), MCP stdio
(`megabrain_ask` · `megabrain_grep` · `megabrain_search` · `megabrain_index` — §5.1), HTTP
(`megabrain studio`, which also serves the studio UI), and the Python API
(`megabrain.search/…`, lazy imports, `py.typed`).

| command | LLM? | latency | use |
|---------|------|---------|-----|
| `search` | no | ~10–200 ms | complete bundle: CORE full code + RELATED map (`--full` for RELATED bodies) |
| `brief` | **no** — the prose was written at study time | ~3–5 ms warm | the repo's MENTAL MODEL for a question: cards + relations + interfaces, almost no code (§4.5) |
| `ask`   | 1 chat call | ~6–25 s | narrated walkthrough, verbatim code spliced at each citation |
| `get` | no | <10 ms | one file or symbol |
| `study` | 1 chat call **per file**, cached by interface | ~26 s / 24 files cold, 0 s unchanged | write the cards `brief` reads (§4.5) |

---

## 2. Index time

### 2.1 Chunkers (`megabrain/chunkers/`)

All chunking sits behind one contract (`chunkers/base.py`): `chunk_file(relpath,
source) -> FileResult` — chunks + symbols + skeleton, **partition-guaranteed**.

Split-then-merge over the AST (the cAST recipe, arXiv 2506.15655): walk top-level
nodes (comment/blank gaps attach to the following unit), **merge** small units up to
a budget of **4000 non-whitespace chars**, **split** oversized ones (big class →
class-header + per-method chunks; big function → `part k/n` blocks; unsplittable
giants → line windows). Every chunk carries a **breadcrumb**
(`repo > path > class Sig > def method(sig)`) that is prepended to the embedded text
(contextual retrieval).

- `python.py` — stdlib `ast`.
- `treesitter.py` — the same algorithm parameterized by a **`LangSpec`** (grammar,
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
- **`SYMBOL_SCHEMA`** (`indexing/_resymbol.py`) — a chunker that learns to see a new
  declaration changes nothing for an already-indexed repo, since the indexer revisits
  a file only when its bytes change. Bumping the marker re-extracts the symbols of
  unchanged files on the next plain `index`, with no embedding calls (measured: seven
  repos, +2 000 symbols, `changed=0`). Symbols only — a change to where a file may be
  CUT still needs `--force`, because those rows carry vectors.
- **Import/call graph** (`graph.py`) — Python: `from pkg.x import Y` + call sites to
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

### 2.5 forge — self-authored chunkers (`forge/`, repo-local strategies)

`megabrain forge <repo>` closes the custom-strategy loop: the engine detects the
repo's uncovered text extensions (deterministic census — no LLM), has an LLM
(the `ask` provider stack; `MEGABRAIN_FORGE_MODEL` to pin) write a
`ChunkStrategy` from the contract source (`chunkers/base.py`, verbatim) plus
real sample files, and accepts it **only** after it chunks every matching file
in the repo with a clean `validate_partition` — failures feed a repair loop
(≤3 attempts), so unvetted code can never install. This keeps the hard rules
intact: the LLM writes code once, at forge time, gated by the partition oracle;
retrieval stays LLM-free.

Vetted modules live in `<repo>/.megabrain/strategies/<ext>.py` and load
automatically on every `index_repo` — including the 60 s auto-refresh — so
forged extensions never fall out of the index. Loading executes repo-provided
code, so it is **trust-gated**: a module only loads when its sha256 matches the
entry in the *user-level* store `~/.megabrain/trust.json` (which a cloned repo
cannot write). forge records the sha on install; `megabrain trust <repo>`
approves hand-written modules; any edit un-trusts the file (skipped with a loud
warning) until re-approved. The oracle guarantees the *current* corpus — a
future file that breaks a forged strategy surfaces in the index stats'
`partition_violations`, never silently.

Surfaces: CLI `megabrain forge [--list|--dry-run|--ext .x]` / `megabrain trust`,
MCP `megabrain_forge` (`list_only`, `dry_run`, `ext`). Real run on pallets/click:
`.toml` (11 files) + `.yaml` (8 CI workflows) both forged first-attempt in ~28 s;
"which workflow runs the test suite" went from a total miss to
`.github/workflows/tests.yaml` at #1.

**Specialization (`--specialize`, `forge_specialize.py` + `forge_eval.py`) is a
measure-only toolkit — NO LLM.** For a covered file type the generic chunker
splits poorly, a human writes a `ChunkStrategy` and the engine decides whether
it earns a place. `detect_specialization` diagnoses three shapes (dominant
dict/list **table**, **blob** >55% of a file in one chunk, **line-window**
fallback); `gate_strategy(root, source, ext)` measures the hand-written
candidate against a literature-tuned baseline (`lit_baseline`: the AST chunker
re-budgeted to 2000, arxiv 2605.04763) and installs it trust-gated only on a
measured win. The gate (`forge_eval`):

- `probe_spans` derives neutral (query, span) pairs from the file's own
  structure (python ast dict-entries/defs; generic blank-line blocks otherwise)
  — no labels, no LLM, chunker-independent.
- `ab_gate` indexes baseline vs candidate for real and measures **rank-aware
  span-IoU** (the file's *top-ranked* chunk vs the true span — what retrieval
  actually surfaces) + global hit@k on EVERY file the candidate changes. WIN
  needs pooled IoU lift ≥ 0.01 · hit@1 held · no per-file regression · no
  micro-chunking (median chunk ≥ 100 nws, checked before indexing). The
  granularity floor + rank-aware IoU exist because an early best-IoU-over-all-
  chunks metric let a median-1-line micro-chunker score a fake pooled 0.55.

**Why no LLM.** It used to generate these; across sinatra, requests, sdk-server
and the engine itself the generated chunkers LOST to the deterministic
lit-2000 recipe and to the default, so the path was removed. The deeper,
load-bearing finding: on the sdk-server golden (the only human-verified query
set) **no chunk budget beats 4000** — R@1 4000=0.86 · 2000=0.82 · surgical
blob-split=0.77. Tighter chunks lift span-IoU (navigation — less to read) but
LOWER retrieval ranking, because the 4000 merge concentrates a file's evidence
and that is what wins R@1. So `DEFAULT_BUDGET=4000` is a genuine optimum;
specialization is an honest win only for its navigation objective, on the rare
pathological file (a lit-2000 chunker on sinatra's many-method classes lifted
span-IoU 0.037 → 0.115 with hit@1 held). Do not chase it on ordinary code.

---

## 3. Query time — retrieval (no LLM)

`retrieval/` (scoring in `scoring.py`, assembly in `bundle.py`, exposed through
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

### 3.2 Issue mode (long queries — bug reports, >25 ident tokens)

Three extra deterministic signals (no LLM), with the expensive lanes **cached on
`SearchState`** for warm servers:

- **Variant ensemble** — title / traceback / fenced-code / identifier-bag views,
  embedded in one batch call, RRF-merged (full-issue ranking double-weighted).
- **Traceback grounding** — Python `File "x.py", line N` **and** JS/TS
  `at fn (src/x.ts:12:5)` frames pin files and enclosing-function spans with tiered
  bonuses; explicit source paths (`.py/.ts/.js/.go/.rb/.rs/.php/…`) and backticked
  identifiers ground through a symbol cascade (exact → lowercase → dotted-suffix).
- **Entity-ID BM25 lane** — postings-based sparse channel over each file's path +
  symbol names + signatures, RRF-merged. Issue-mode only: it raised SWE-bench recall
  but cost golden completeness on short queries.

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

**LLM rerank (`retrieval/rerank.py`, the `llm_rerank` lane, layered ON the prune).**
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

### 3.4 Flow cache — self-caching workflow retrieval (`flows.py`, on by default)

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
`retrieval` stream event carries them). A repo can commit **starter queries**
at `<root>/.megabrainqueries` (one per line, `#` comments; `GET /queries`):
the studio renders them as one-click chips in Ask with an explicit **Warm
all** button — the newcomer flow: open the repo, click through the starters,
see the main workflows, and leave them cached for everyone.

---

## 4. `ask` — narration with verbatim code (`ask.py`)

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

- **`claude`** (`providers_claude.py`, extra `megabrain[claude]`) — the Claude Agent
  SDK drives the Claude Code CLI: a logged-in **subscription** narrates on Claude
  Code credits with zero keys; `ANTHROPIC_API_KEY` bills the API instead. The
  narration transport pins pure narration (no tools + an explicit disallow list + a
  no-tools preamble; without it the agent runtime sometimes tried to "search the
  codebase" and burned the turn). Streaming via partial-message events — same
  `(text, finish_reason)` contract as the SSE path. ask v2 sub-agents use a second
  transport (`agent_stream`): megabrain's retrieval tools register as an in-process
  MCP server and the SDK runs the tool loop itself — builtins stay disallowed.
- **`openrouter`** (`providers.py`, urllib-only) — any OpenAI-compatible endpoint;
  `MEGABRAIN_CHAT_BASE_URL` points it at native APIs or local servers. For ask v2,
  `stream_chat(with_tools=True)` also accumulates fragmented `delta.tool_calls`
  and the loop runs in `ask_agents`.

**Embeddings never use this switch** — Anthropic has no embeddings API, so
index/query always need OpenRouter or a local embed endpoint. The two lanes are
independent by design (hybrid local-embed + Claude-narrate works).

### 4.2 ask v2 — adaptive multi-agent synthesis (`ask_agents.py`)

Broad questions dilute a single narrator, so `ask` branches on **retrieval shape**
(no LLM, ~0ms — `classify_bundle`): several CORE files inside the tier1 gap,
candidates spread across ≥3 top-level dirs, ≥4 RELATED files near score parity, or
an issue-length query → **broad**. Scoped questions never pay the fan-out.

The fan-out (`run_agents`, gated to ≤4 sub-agents, ≤3 tool rounds each):

1. **Repo map** — every indexed path + its skeleton docline (from the file matrix
   already in `SearchState`), budget-capped; goes in EVERY agent's prompt.
2. **Plan** — one cheap LLM call (the ask model) splits the question into scoped
   sub-queries and assigns each agent a slice of the shared candidate list
   (fail-open → deterministic top-level-dir clustering → single-agent ask).
3. **Parallel sub-agents** (a ThreadPool over the slices) — each
   knows it is "sub-agent k of n" whose answer will be synthesized, sees the repo
   map + its chunks with **GLOBAL `[[k]]` numbering**, and may call retrieval
   **tools** (`search_more` / `get_file` / `get_symbol` — the backends are
   `search_with_state`/`get_code`, so rule 1 holds: no LLM in retrieval).
4. **Synthesis** — a streamed parent call merges the partials into one walkthrough,
   preserving the global citations, so the UNCHANGED splice pipeline grounds every
   block verbatim and dedupes repeated spans.

Everything emits JSON events (`plan`, `agent_start/delta/tool/done`,
`synthesis_delta` with spliced markdown, `done`) through `stream_events` — the CLI
prints status lines, `/ask/stream` forwards them as SSE, buffered callers (MCP,
`POST /ask`) just take the final dict. Fail-open chain end to end: fan-out error →
single-agent ask → full bundle.

### 4.5 `brief` — the mental model, and why it does not rank (`atlas/`)

Full detail, with the numbers and the field notes: **[docs/BRIEF.md](docs/BRIEF.md)**.

`search` returns code; `brief` returns the **model of the system** — what each relevant
file *is*, how the files connect, what they declare — with almost no bodies. It exists
because an agent handed 4 000 tokens of code has to *reconstruct* the mental model before
it can act; the brief hands it over already built (~950 tokens at `--limit 3`).

The design is one split, and everything follows from it:

| part | produced | when | can it be stale or wrong? |
|---|---|---|---|
| the prose (**card**) | a chat model, oracle-gated | **index** time, cached | the only model-written text |
| `→ uses` / `← used by` | the stored `edges` table | **query** time, live | no — it is the index |
| the interface | the `symbols` table | query time | no — from the AST |

**A card may never describe another file.** Not a style rule: a claim about another file
goes stale when *that* file changes, and nothing would regenerate this card. Relations
belong to the graph, and the graph is re-read on every query — so they cannot rot.

**Selection is the bundle, not a second ranker.** `brief_repo` calls
`search_with_state` — the same deterministic engine `search` and `ask` use — and only
changes the *presentation* of the file list it returns. This was not the first design, and
the first one was wrong in a way worth keeping: it ranked by cosine over one vector per
card, and on a real repo (`pineward`, *"how does the VDF proof get validated?"*)
`validate.py` — the file that calls `verify_vdf` — landed **5th**, below a file that
merely shares the question's vocabulary. At `--limit 3` it disappeared.

The cause is structural: **one vector per file averages everything the file does.**
`validate.py` has seven responsibilities and VDF is one, so its card vector dilutes VDF to
nothing. That is precisely why §3.1 fuses chunk cosine with the file skeleton
(`file_fusion_w = 0.5`) and §3.3 adds two recall floors, rather than ranking on file
vectors. Deleting the parallel ranker fixed it *by inheritance* — the brief now gets the
fusion, the test penalty and both floors for free, so **rule 2 holds here by construction
instead of by a second implementation that has to remember it.** It also removed the card
embeddings entirely: cards never rank, so the `cards` table has no vector column and
`study` costs no embedding calls.

**Cached by INTERFACE, not by content.** The key is `sha256(CARD_SCHEMA, model, skeleton)`
— not the file's sha. A card describes what a file *declares*, so editing a body leaves
the skeleton, the key and the card untouched; changing a signature regenerates exactly the
file whose interface moved. `CARD_SCHEMA` behaves like `EDGE_SCHEMA` (§2.3): a bump makes
every card stale and the next `study` re-authors them with no `--force`.

**The oracle (`atlas/oracle.py`, no LLM)** — the same stance as forge: the model proposes,
a deterministic check disposes. Every `backticked` name must appear in the skeleton the
prompt showed; no other file may be named; length is bounded and at least one real name
must be cited. Reject → one retry with the problems listed → still reject → the card
**degrades to the raw skeleton**, flagged `degraded`. Worse prose, zero lies.

> **Field note.** The grounding set was first the file's top-level *symbol names*, and
> that rejected 5 of 24 cards on a real repo — including the most relevant file. The
> rejected prose was good; it backticked `x`, `y`, `t`, `pi`, the **parameters of
> signatures the prompt itself contained**. Grounding on the skeleton (the model's actual
> input) took degradation 5 → **0**. The grounding set must be the model's input, never a
> narrower view of it.

**Failure is a missing map, never a failed index.** `build_index(llm=True)` composes the
two passes in the use-case layer — not chained by each transport, so no surface can
disagree about what "index with the LLM" means — and the card pass runs *after* the index
is committed. A dead provider therefore leaves the index intact, the exit code 0, and the
shortfall **reported** (`study_error`, or the `degraded` count) rather than raised.

---

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
- **HTTP** (`frontends/http.py`, stdlib `http.server`, warm state, db-mtime auto-reload):
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

## 6. Graph — the repo as a knowledge graph (`megabrain/graph.py`, numpy-only)

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
them are enforced by executable tests rather than documented: `retrieval/` may not import
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
                       (ignore · queries · models.{narrator,rerank,study})
      __init__.py      public API: lazy __getattr__ + a TYPE_CHECKING block, so
                       `import megabrain` costs no numpy (pinned by a test)

  L1  contracts/       EVERY cross-boundary payload, TypedDict only, zero logic
                       chunk · bundle · brief · file · graph · repo · scan · prune

  L2  storage/         PERSISTENCE — the ONLY package allowed to write SQL
        store.py         connection + schema; one table per object
        schema.py        DDL + versioned migrations (chunks · files · symbols ·
                         edges · meta · flows · cards)
        _chunks · _files · _symbols · _graph · _flows · _cards (the study cards,
                         no vector column: cards never rank)
        _blobs.py        the untyped sqlite↔numpy boundary
        locate.py        resolve_root + INDEX_FILE — the layout lives in ONE line
      providers/       model APIs
        embeddings.py    OpenAI-compatible /embeddings; batch width detection,
                         index-set validation, content-addressed disk cache
        http · _retry · _urllib · _wire · _width · _config · cache
        chat/            L4 — nothing under retrieval/ may import this
          base.py          ChatProvider Protocol · openai_compat.py · router.py

  L3  chunkers/        CONTENT → CHUNKS behind one partition-guaranteed contract
        cast.py          the ONE split-then-merge engine · units.py the language seam
        _spans · _split · _merge · _balance · _breadcrumb · _signature · _pysymbols
        python.py        stdlib ast · model.py Chunk/Symbol/FileResult + validate_partition
      indexing/        BUILD the index — 3 phases = 3 functions
        indexer.py       orchestration · discover.py the walk · _plan.py what to do
        _embed.py        the GLOBAL batch embed (one network call per pass)
        _write.py        rows + prune_orphans (GONE vs SKIPPED) · _graph.py edges
        edges · _imports · _calls   import/call resolution (python)
        strategies.py    ext → Strategy registry (OCP) · builtin.py the shipped one
        _exclude.py      megabrain.json ignores + the legacy dotfiles
        _gitignore.py    the repo's own .gitignore (on by default, opt-out)
      retrieval/       ANSWER queries — NO LLM IN HERE (rule 1, enforced by a test)
        search.py        the neutral primitive · params.py every knob, frozen
        state.py         SearchState + load_state (warm matrices)
        paths.py         is_test / is_demo / ident_tokens — path vocabulary
        scoring/         pipeline · lane · lanes (TestPenalty, LexicalBoost) ·
                         _fusion (the BASE: dense + 0.5·file) · _space · context
        bundle/          assemble · _rank · _related · _anchors · floors (the two
                         recall floors) · _convert
        render/          markdown · _lang
      knowledge/       THE GRAPH (§6) — candidates + annotations, never ranking
        build.py         RepoGraph + load_graph (near/out/into adjacency)
        communities · gods · surprises · paths (BFS) · labels · views
        uses · usesites · carriers · tolls · aliases · source · snips

  L4  atlas/           THE MENTAL MAP (§4.5) — an LLM at INDEX time, never at query
        author.py        writes one card per file  ← the only module here with an LLM
        oracle.py        accepts/rejects a card against the skeleton it was shown
        _plan.py         CARD_SCHEMA + the cache key (schema, model, skeleton)
        _prompt.py       the prompt and its one retry
        brief.py         QUERY time, 0 LLM: takes the bundle's file list as-is
        _assemble.py     narrative order (graph BFS) + one entry's relations/interface
        render.py        Brief → terminal markdown
      enrich/          Bundle → Bundle, opt-in, fail-open to the input
        rerank.py        the judge lane: the model returns IDS, never code
        _batches · _cards · _prompt · _verdict
      ask/             NARRATE — the only layer that talks to an LLM at query time
        narrator.py · splice.py (rule 5) · agents.py · _subagent · _pool ·
        _candidates · citations · events · prompt · stream · _rules · _block ·
        repair.py + _broken.py  (a citation that resolved to nothing, re-asked)
      flows/           the cached-walkthrough lane (cache · serve · match · covers ·
                       freshness · chrome)

  L5  usecases/        ONE FILE PER VERB — every transport calls THESE
        build.py         index (+ llm=True composes study — one meaning, N surfaces)
        study.py         write the cards · brief.py the mental model
        search · ask · get · scan · repos · freshness · _flows · _registry
      transports/      SURFACES — thin adapters: args → use-case → render
        cli/            main.py + commands/{index,study,scan,search,brief,ask,get,
                        graph,studio}.py — one module per verb, no branch in main
        mcp/            server · protocol · dispatch (a TABLE of 3-line handlers) ·
                        tools (the three) · schema (inputSchema GENERATED from
                        contracts/tools.py) · arguments · answers · __main__
        http/           app · router (a TABLE, never a chain of ifs) · messages
                        (the two records) · replies (the Reply factories) · _target
                        (wire parsing) · _handler · _writer · sse · security
          routes/         query (search · brief · get · symbols) · asking · indexing ·
                          graph · project · meta · scanning · static
studio/                the studio's TypeScript workspace (esbuild → transports/http/ui/)
  src/views/           ask · brief · search · graph · files · adding
```

Not yet ported (deliberate, tracked): `forge/` (phase 16) · the `treesitter` / `php` /
`markdown` chunkers and the languages they carry · the issue-mode lane.

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
  openai-3-large and bge-m3 on code recall (`evals/embed_bakeoff.py`).
- **Ask-model bakeoff**: qwen3-coder ≈ claude-haiku on citation selection at ~5×
  lower cost (`evals/ask_bakeoff.py`).
- **SWE-bench Lite localization** (no training): retrieval-only Acc@1 ≈ 0.52 / @5 ≈
  0.83 — on par with the trained CodeRankEmbed retriever; ask-cited-files Acc@1 ≈
  0.69–0.71, in range of SWE-bench-trained SweRankEmbed-Large.
