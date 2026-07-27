# Reference

Lookup tables. Learning megabrain? → **[Guide](GUIDE.md)**. Trying to do a specific
thing? → **[Recipes](RECIPES.md)**.

Every table here was verified against `src/megabrain/`.

- [CLI](#cli) · [MCP tools](#mcp-tools) · [HTTP API](#http-api)
- [Environment variables](#environment-variables) · [Config files](#config-files)
- [Graph](#graph) · [Python API](#python-api)

---

## CLI

Every verb takes a repo path, and it may be **any sub-path inside an indexed repo** —
megabrain finds the root from `.megabrain/` upward and scopes retrieval to files under it.
The one exception is `index`, which never resolves upward: indexing a path that has no
index yet is the whole point.

| command | what it does |
|---|---|
| `megabrain index [path]` | build/update the index — incremental by sha256 |
| `megabrain scan [path]` | census only: what WOULD index + every skip with its reason |
| `megabrain search <query> [path]` | retrieval, no LLM: CORE code + RELATED map |
| `megabrain ask <question> [path]` | narrated walkthrough with the real code spliced in |
| `megabrain grep <task> [path]` | where to edit: files, symbols, exact line ranges — no model |
| `megabrain get <file> [path]` | print one file (or one symbol) |
| `megabrain graph [path]` | the repo as a knowledge graph |
| `megabrain studio` | the web UI + JSON API on one port |
| `megabrain install` | register the MCP server with every assistant detected on this machine |

### Flags

| command | flag | effect |
|---|---|---|
| `index` | `--force` | re-chunk and re-embed every file, ignoring the sha cache (after an embed-model change) |
| | `--exclude GLOB` | skip paths matching GLOB; repeatable |
| | `--quiet` | no progress output (progress goes to stderr, the report to stdout) |
| `scan` | `--json` | machine-readable |
| `search` | `--path-filter PREFIX` | only files under PREFIX |
| | `--code` / `--docs` | code only, or prose only — never a blend. Omit to let them compete |
| | `--full` | include the code bodies (default: the map only — files, spans, symbols) |
| | `--rerank` | one judge call reorders RELATED by the task's edit surface; never drops a file |
| | `--expand` | a model names the identifiers your wording missed; the symbol table adds the files defining them. Buys RECALL where `--rerank` buys ORDER; only ever ADDS. Measured safe but not yet measured useful — see GUIDE §`--expand` |
| | `--json` | the `Bundle` contract |
| `ask` | `--path-filter PREFIX` | only files under PREFIX |
| | `--docs` | explain markdown instead of code |
| | `--quiet` | suppress the progress trace (it goes to stderr; the answer goes to stdout) |
| `grep` | `--path-filter PREFIX` | only files under PREFIX |
| | `--why` | one model call: a note per site, plus the site no literal search can reach (measured: 0.05 s → 1.3 s) |
| | `--quiet` | the rows only, no retrieval trace |
| `get` | `--symbol NAME` | just that symbol |
| | `--outline` | the file's symbols only, no code |
| | `--json` | machine-readable |
| `graph` | `--node FILE` | one file's neighbourhood |
| | `--from FILE --to FILE` | the route between two files |
| | `--code` | with `--from/--to`: the real code at each hop |
| | `--no-labels` | skip the cached model call that names the clusters |
| | `--json` | machine-readable |
| `studio` | `--host H` · `--port N` | default loopback-only (`127.0.0.1`) · `2137` |
| | `--token T` | require `Authorization: Bearer T` (default `$MEGABRAIN_API_TOKEN`) |
| | `--readonly` | serve queries but refuse to index, so a public box cannot be billed by a visitor |
| | `--rate-limit N` | at most N requests per minute per caller |
| `install` | `--list` | show what's detected and where, change nothing |
| | `--platform NAME` | only this one (`claude` · `codex` · `antigravity` · `cursor` · `windsurf` · `gemini`); written even if undetected |
| | `--remove` | unregister megabrain, leaving every other server in place |

---

## MCP tools

```bash
megabrain install                                              # every assistant detected
claude mcp add megabrain -- python3 -m megabrain.transports.mcp # or by hand
```

**Four tools, and the smallness is deliberate.** Every tool costs the calling agent
context and a routing decision, and the host already has Read, Grep and an editor — so the
surface carries only what megabrain alone can do. Each `inputSchema` is **generated** from
`contracts/tools.py`, so a parameter cannot exist on the wire without existing in the
dispatch.

Every tool takes `repo_path` (any sub-path works — the root is auto-detected).

| tool | returns | parameters |
|---|---|---|
| **`megabrain_grep`** | WHERE TO LOOK for a change: the files to open, the symbols in them worth opening, and each one's **exact line range** from the index. **No model by default** (~50 ms) — and it quotes no code, because your editor opens the file anyway. Name the identifiers you already know. | `task` *(req)* · `scope_path` · `why` *(default `false`)* |
| **`megabrain_ask`** | The whole flow behind a question — or behind a change you are about to make — narrated with the REAL code spliced in verbatim. The narrator **opens whatever the retrieved chunks left unexplained** and keeps reading until the answer is complete; the definition of every helper the prose names and the tests that PIN what it describes are then cited with no model call. The prose is narration, so check it against the code it quotes. | `query` *(req)* · `scope_path` · `content` |
| **`megabrain_search`** | The task's whole edit surface as a MAP: the files that answer it ranked, each with its best span (true line numbers) and the symbols it declares, plus the anchors a change must touch and the tests that pin the behaviour. ~2 700 tokens against ~8 100 with bodies. | `task` *(req)* · `scope_path` · `content` · `bodies` *(default `false`)* · `rerank` *(default `false`)* · `expand` *(default `false`)* |
| **`megabrain_index`** | Build or refresh the index. Incremental by content hash, so a warm re-index costs seconds. | `force` *(default `false`)* |

It was briefly five. `megabrain_code` and `megabrain_replace` were measured across five
tasks in three languages and **removed**: what carried the value was the narrator opening
files until it had the whole flow, and that now belongs to `ask` itself; the edit machinery
kept being thrown away by the readers it was built for.

---

## HTTP API

Served by `megabrain studio` — the UI at `/` and the JSON API on the same port. Every route
accepts an optional `?repo=` / `"repo"` — absent means the boot repo.

| route | returns |
|---|---|
| `GET /health` | liveness + the index's shape (`?freshness=1` also hashes disk — the right cost for a button, the wrong one for a probe) |
| `GET /config` | `{version, readonly, rate_limit, auth}` — what kind of server this is |
| `GET /repos` | every repo indexed on this machine, with live counts |
| `GET /project` | what a REPOSITORY decided about itself: its starter `queries` and its `models` (`narrator` · `rerank`) |
| `GET /scan?path=` | the add-repo census |
| `GET /get?file=&symbol=` | one file's real code |
| `GET /symbols?file=` | that file's outline alone — what a file tree draws |
| `GET /graph?mode=&node=&source=&target=` | the knowledge graph (`map` · `node` · `path`) |
| `POST /search {query, repo?, path_filter?, content?, rerank?, expand?}` | the CORE/RELATED `Bundle` |
| `POST /ask/stream` | the narrated answer as SSE |
| `POST /index/stream {path, force?}` | (re)index with per-file SSE progress |

`--readonly` refuses the mutating routes with a 403. `--token` exempts only `/health`,
`/config` and the UI.

**SSE events** (`/ask/stream`), the same typed set the CLI renders: `retrieval` ·
`planning` · `plan` · `agent` · `narrating` · `delta` · `narrated` · `error` · **`done`**.
`retrieval` arrives **before any model has run** — a sink that stops there already has the
deterministic answer — and `done` terminates the stream on **every** path, so a caller
never has to know which branch answered to know the answer ended.

---

## Environment variables

| variable | default | what it does |
|---|---|---|
| `OPENROUTER_API_KEY` | — | the one key for embeddings + chat |
| `MEGABRAIN_EMBED_MODEL` | `perplexity/pplx-embed-v1-0.6b` | the embedding model |
| `MEGABRAIN_EMBED_BASE_URL` | `https://openrouter.ai/api/v1` | any OpenAI-compatible endpoint (a local one needs no key) |
| `MEGABRAIN_EMBED_API_KEY` | falls back to `OPENROUTER_API_KEY` | key for a non-OpenRouter embed endpoint |
| `MEGABRAIN_CHAT_MODEL` | `anthropic/claude-sonnet-4.5` | the chat model when nothing more specific applies |
| `MEGABRAIN_CHAT_BASE_URL` | `https://openrouter.ai/api/v1` | point chat at a native API or a local server |
| `MEGABRAIN_CHAT_API_KEY` | falls back to `OPENROUTER_API_KEY` | key for a non-OpenRouter chat endpoint |
| `MEGABRAIN_ASK_MODEL` | `google/gemini-3.1-flash-lite` | the narration model |
| `MEGABRAIN_RERANK_MODEL` | `google/gemini-3.5-flash-lite` | the judge lane's model — measured separately, because narration reasons in prose and the judge emits a short id array |
| `MEGABRAIN_ASK_CTX_CHARS` | `200000` | `ask`'s candidate budget — **lower it for local models** |
| `MEGABRAIN_ASK_SPLICE_CAP` | — | cap on spliced code per answer |
| `MEGABRAIN_MAX_AGENTS` · `MEGABRAIN_AGENT_TIMEOUT` | — | the fan-out's width and per-agent deadline |
| `MEGABRAIN_API_TOKEN` | — | default for `studio --token` |

**Precedence for every model:** an explicit argument beats `megabrain.json`, which beats
the environment, which beats the built-in default. The file wins over the env var on
purpose — a committed config travels to whoever clones the repo, while an env var lives in
one shell and is invisible to everyone else.

Changing the embed model auto-triggers a full re-embed on the next `index`, so vectors can
never silently mismatch.

---

## Config files

| path | what it is |
|---|---|
| **`<repo>/megabrain.json`** | what the repository decides about ITSELF: `ignore` · `gitignore` · `queries` · `models` (`narrator` · `rerank`). **Visible, not a dotfile** — it is committed and meant to be found and edited by whoever clones the repo, while `.megabrain/` beside it is machine state nobody reads. The dot marks what you ignore |
| `<repo>/.gitignore` | **also read, and on by default**: what the repo already declared is not its source. shipway compiles into `bin/`, which the universal exclude list cannot cover (`bin/` is real code in a Python or Rust project) — 122 of its 196 indexed files were that output, giving every `src/` symbol a compiled twin. Set `"gitignore": false` where the repo ignores real source (measured: megabrain-v2's own `evals/`) |
| `<repo>/.megabrain/db.sqlite` | **the whole index** — chunks, vectors, symbols, edges, cards, flows |
| `<repo>/.megabrainignore` | legacy, still read: patterns to skip, one per line. Merged with `megabrain.json`'s `ignore` |
| `<repo>/.megabrainqueries` | legacy, still read: starter questions, one per line, `#` comments. Merged with `queries` |
| `~/.megabrain/registry.json` | every repo indexed on this machine; self-heals when an index vanishes |

```json
// megabrain.json — nothing in it is required
{
  "ignore":  ["dist", "vendor/**"],
  "gitignore": true,
  "queries": ["how does the retry policy work?"],
  "models":  { "narrator": "google/gemini-3.1-flash-lite",
               "rerank":   "google/gemini-3.5-flash-lite" }
}
```

A repository with no config is fully usable; a malformed one falls back **and says so**
(`malformed: true` on `GET /project`) rather than looking identical to having none; a field
of the wrong shape is ignored on its own without taking the rest of the file down.

Deleting an index: `rm -rf <repo>/.megabrain`. There is no command for it, on purpose.

---

## Graph

| knob | default | what it does |
|---|---|---|
| `SEM_EDGE_MIN` | `0.80` | min cosine for a dashed semantic edge |
| `SEM_TOP_K` | `3` | semantic edges per file — keeps the map sparse |
| `SEM_WEIGHT` | `0.5` | weight of a semantic edge in label propagation (structural = 1.0) |
| `SURPRISE_MIN` | `0.85` | min cosine for a "surprising connection" |
| `hub_damping(d)` | `1/log2(1+d)` | what a vote through a file of degree `d` is worth |
| `PLUMBING_TOLL` / `HUB_TOLL` | `4` / `3 + (d − floor)` | route transit cost for `__init__.py` and tests / for a hub |
| `--no-labels` | off | skip the cached LLM community-labelling call |

**Languages.** Always on: **Python** (`.py .pyi`), **TypeScript/JavaScript**
(`.ts .tsx .js .jsx .mjs .cjs`) and **Markdown** (`.md .markdown .mdx`). With
`pip install megabrain[languages]`: **Ruby** (`.rb .rake .gemspec`), **Go**, **Rust**,
**PHP**, **C** (`.c .h`), **C++** (`.cpp .cc .cxx .hpp .hh .hxx`), **Java**, **C#** —
the registry adds each one only if its grammar imports, so a missing wheel costs that
language and nothing else.

Structural **edges** are extracted for Python and TypeScript/JavaScript. The others
chunk, search and outline without a graph: retrieval never depended on it, and the graph
is an annotation lane an extractor can be added to later.

A file no chunker claims is NAMED in the census by extension (`4 .swift · 1 .kt`), and
indexing a path where nothing at all is readable is an error (`nothing_to_index`) rather
than a successful index of nothing.

Communities come from deterministic weighted label propagation (numpy only) — same
input, same output, every run.

**Why the damping.** Undamped propagation collapses on any repo with a hub: on the
1210-file Anthropic SDK, whose `_models.py` has 511 dependents, one community held
**1180 files (97.5%)**. Damping a vote by the degree of the file it comes from — a vote
through a file everything imports says less about where you belong — drops that to
**108 (8.9%)** with 112 clusters of three files or more, and singletons stay at 1.7%.
`1/d` fragments harder (294 clusters) for no gain, so the gentlest weighting that breaks
the flood is the one that ships.

**Routes are costed, not just ordered.** Plain breadth-first search connects any two
files through the logger, the config or a package `__init__`, because it has no concept
of a boring hub. Hubs, package plumbing and test files pay a toll; semantic edges cost
more than structural ones; the endpoints are exempt. Each hop reports the symbol that
carries it — AST-verified, receiver-checked — with the call site and the definition.

---

## Python API

```python
from megabrain import index_repo, search, load_state, search_with_state
from megabrain.usecases import ask, grep, get_code, scan
```

**`megabrain`** — the public surface. Every name is lazy: `import megabrain` loads no numpy
and no tree_sitter, because the module resolves on first attribute access.

| name | purpose |
|---|---|
| `index_repo(root, *, embedder, force, exclude, strategies, on_progress)` | build/update an index, returns stats |
| `discover(root, extensions, *, exclude)` | the walk alone: indexable files + every skip with its reason |
| `search(root, query, *, path_filter, content, rerank, expand)` | one-shot `Bundle` — no LLM unless you ask for a lane |
| `load_state(root)` → `SearchState` | load the matrices once, query many times (use it as a context manager) |
| `search_with_state(state, query, *, path_filter, content)` | the bundle, warm |
| `score_chunks(state, query, …)` | the scoring pipeline alone, below the bundle |
| `Store` · `ChunkMeta` | the storage layer and the read-side chunk record — **the only place SQL lives** |
| `Strategy` · `Registry` · `Chunk` · `Symbol` · `FileResult` · `validate_partition` | the custom content-type contract |
| `MegabrainError` · `IndexNotFound` · `EmptyIndex` · `ModelMismatch` · `MissingCredential` · `MissingAPIKey` · `ProviderError` | the error taxonomy |

**`megabrain.usecases`** — the verbs the CLI, MCP and HTTP all call, so a behaviour is
implemented once and three surfaces cannot drift: `ask` · `grep` · `search` ·
`build_index` · `get_code` · `scan` · `freshness` · `starters_for` · `known` · `remember` ·
`resolve_root`. Sync all the way down; the HTTP edge is the only async thing and it calls
into here from a threadpool.

Errors carry a machine `code` **and** keep a familiar base class, so old callers keep
working — `IndexNotFound(MegabrainError, ValueError)`. The package is `py.typed`, checked
under both mypy strict and pyright strict. A custom content type has one hard requirement:
its chunks must form an **exact line partition** of the file, and it is checked, not
trusted.
