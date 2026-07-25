# Reference

Lookup tables. Learning megabrain? → **[Guide](GUIDE.md)**. Trying to do a specific
thing? → **[Recipes](RECIPES.md)**. The mental-model lane in depth? → **[Brief](BRIEF.md)**.

> ⚠️ **The CLI, MCP, HTTP, env-var and config tables below are v3-accurate** (verified
> against `src/megabrain/`). The **Graph** and **Python API** sections still describe
> **v2** — several names there have moved or do not exist yet.

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
| `megabrain study [path]` | write the **cards** `brief` reads: one model call per file, cached by interface ([details](BRIEF.md)) |
| `megabrain scan [path]` | census only: what WOULD index + every skip with its reason |
| `megabrain search <query> [path]` | retrieval, no LLM: CORE code + RELATED map |
| `megabrain brief <query> [path]` | the **mental model**: cards + live relations + interfaces, no bodies, no model call |
| `megabrain ask <question> [path]` | narrated walkthrough with the real code spliced in |
| `megabrain get <file> [path]` | print one file (or one symbol) |
| `megabrain graph [path]` | the repo as a knowledge graph |
| `megabrain studio` | the web UI + JSON API |
| `megabrain install` | register the MCP server with every assistant detected on this machine |

### Flags

| command | flag | effect |
|---|---|---|
| `index` | `--force` | re-chunk and re-embed every file, ignoring the sha cache (after an embed-model change) |
| | `--llm` | **also write the mental map** — `study` in the same command. One model call per changed file; the index is committed first, so a provider failure leaves the index intact and reports `study_error` |
| | `--exclude GLOB` | skip paths matching GLOB; repeatable |
| | `--quiet` | no progress output (progress goes to stderr, the report to stdout) |
| `study` | `--model NAME` | override the model for this run (beats `megabrain.json`) |
| | `--force` | rewrite every card, ignoring the cache |
| | `--quiet` | no progress output |
| `scan` | `--json` | machine-readable |
| `search` | `--path-filter PREFIX` | only files under PREFIX |
| | `--code` / `--docs` | code only, or prose only — never a blend. Omit to let them compete |
| | `--full` | code bodies for RELATED files too, not just a map |
| | `--compact` | no code bodies at all — the map only |
| | `--rerank` | one judge call reorders RELATED by the task's edit surface; never drops a file |
| | `--json` | the `Bundle` contract |
| `brief` | `--limit N` | files in the answer (default 10). **3–5 is the sweet spot** — ~950–1 500 tokens |
| | `--json` | the `Brief` contract |
| `ask` | `--path-filter PREFIX` | only files under PREFIX |
| | `--docs` | explain markdown instead of code |
| | `--quiet` | suppress the progress trace |
| `get` | `--symbol NAME` | just that symbol |
| | `--outline` | the file's symbols only, no code |
| | `--json` | machine-readable |
| `graph` | `--node FILE` | one file's neighbourhood |
| | `--from FILE --to FILE` | the route between two files |
| | `--code` | with `--from/--to`: the real code at each hop |
| | `--no-labels` | skip the cached model call that names the clusters |
| | `--json` | machine-readable |
| `studio` | `--host H` · `--port N` | default loopback-only · `2134` |
| | `--token T` | require `Authorization: Bearer T` (default `$MEGABRAIN_API_TOKEN`) |
| | `--readonly` | serve queries but refuse to index — and refuse `llm: true` with a 403, so a public box cannot be billed by a visitor |
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

**Three tools, and the smallness is deliberate.** Every tool costs the calling agent
context and a routing decision, and the host already has Read, Grep and an editor — so the
surface carries only what megabrain alone can do. Each `inputSchema` is **generated** from
`contracts/tools.py`, so a parameter cannot exist on the wire without existing in the
dispatch.

Every tool takes `repo_path` (any sub-path works — the root is auto-detected).

| tool | returns | parameters |
|---|---|---|
| **`megabrain_ask`** | A narrated walkthrough of the whole relevant flow with the real code spliced in verbatim — the code cannot be invented; the prose around it is narration, so check its claims against the code it quotes. | `question` *(req)* · `scope_path` · `content` (`code` default · `docs`) |
| **`megabrain_search`** | The task's whole edit surface: the files that answer it ranked, each with its best span and body under a true-line-number gutter, plus the anchors a change must touch and the tests that pin the behaviour. | `task` *(req)* · `scope_path` · `content` · `bodies` *(default `true`)* · `rerank` *(default `false`)* |
| **`megabrain_brief`** | The **mental model** before any code: one card per file saying what it is for, import relations rendered live from the graph, and each file's interface — no bodies, no model call, milliseconds. The cheap **first** call on an unfamiliar repo. Needs `megabrain study` to have run once. | `question` *(req)* · `limit` *(default 10, capped 30)* |

---

## HTTP API

Served by both `megabrain studio` (with the UI at `/`) and `megabrain serve-api`
(headless). Every route accepts an optional `?repo=` / `"repo"` — absent means the boot
repo.

| route | returns |
|---|---|
| `GET /health` | liveness + the index's shape (`?freshness=1` also hashes disk — the right cost for a button, the wrong one for a probe) |
| `GET /config` | `{version, readonly, rate_limit, auth}` — what kind of server this is |
| `GET /repos` | every repo indexed on this machine, with live counts |
| `GET /project` | what a REPOSITORY decided about itself: its starter `queries` and its `models` (`narrator` · `rerank` · `study`) |
| `GET /scan?path=` | the add-repo census |
| `GET /get?file=&symbol=` | one file's real code |
| `GET /symbols?file=` | that file's outline alone — what a file tree draws |
| `GET /graph?mode=&node=&source=&target=` | the knowledge graph (`map` · `node` · `path`) |
| `POST /search {query, repo?, path_filter?, content?, rerank?}` | the CORE/RELATED `Bundle` |
| `POST /brief {query, repo?, limit?}` | the `Brief`: cards + live relations + interfaces. `limit` clamped 1–30. **404 `study_not_found`** if the repo was never studied, so a client can tell "run `megabrain study`" from a real failure |
| `POST /ask/stream` | the narrated answer as SSE |
| `POST /index/stream {path, force?, llm?}` | (re)index with per-file SSE progress. `llm: true` also writes the cards: `{"type":"card",…}` frames, and the terminal `done` carries `study` (or `study_error`) |

`--readonly` refuses the mutating routes with a 403 — **including `llm: true` on
`/index/stream`**, since that spends a model call per file and a public box must not be
billed by whoever ticks a box. `--token` exempts only `/health`, `/config` and the UI.

**SSE events** (`/ask/stream`): `retrieval` · `cached` · `classified` · `planning` ·
`plan` · `agent_start` · `agent_delta` · `agent_tool` · `agent_done` · `agent_error` ·
`synthesis_start` · `synthesis_delta` · `length` · `bundle` · `error` · **`done`**.
`done` terminates the stream on **every** path — a sink never has to know which branch
answered to know the answer ended.

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
| **`MEGABRAIN_STUDY_MODEL`** | `google/gemini-3.1-flash-lite` | the model that writes the **cards** (`study` / `index --llm`). Its own knob because the cost SHAPE differs: narration is one call per question, study is one call per **file per index** ([why](BRIEF.md#the-model)) |
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
| **`<repo>/megabrain.json`** | what the repository decides about ITSELF: `ignore` · `queries` · `models` (`narrator` · `rerank` · `study`). **Visible, not a dotfile** — it is committed and meant to be found and edited by whoever clones the repo, while `.megabrain/` beside it is machine state nobody reads. The dot marks what you ignore |
| `<repo>/.megabrain/db.sqlite` | **the whole index** — chunks, vectors, symbols, edges, cards, flows |
| `<repo>/.megabrainignore` | legacy, still read: patterns to skip, one per line. Merged with `megabrain.json`'s `ignore` |
| `<repo>/.megabrainqueries` | legacy, still read: starter questions, one per line, `#` comments. Merged with `queries` |
| `~/.megabrain/registry.json` | every repo indexed on this machine; self-heals when an index vanishes |

```json
// megabrain.json — nothing in it is required
{
  "ignore":  ["dist", "vendor/**"],
  "queries": ["how does the retry policy work?"],
  "models":  { "narrator": "google/gemini-3.1-flash-lite",
               "rerank":   "google/gemini-3.5-flash-lite",
               "study":    "google/gemini-3.1-flash-lite" }
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

**This build reads `.py` and `.pyi` only.** The other chunkers have not been ported yet,
and the census says so by name: point it at a TypeScript repository and it reports
`215 .ts · 92 .tsx` under "nothing here can be indexed yet" rather than an empty result.
Indexing such a path is an error (`nothing_to_index`), not a successful index of nothing.

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
from megabrain import index_repo, load_state, search_with_state, prune_search
from megabrain.ask import ask, render_ask
```

| name | purpose |
|---|---|
| `index_repo(root, *, force, exclude, strategies, scan_filters)` | build/update an index, returns stats |
| `load_state(root)` → `SearchState` | load the matrices once, query many times |
| `search_with_state(state, query, *, path_filter)` | the bundle, warm |
| `search(root, query)` | one-shot bundle |
| `prune_search(state, query, *, with_text, include_pruned, only_docs, exclude_docs)` | flat ranked signal chunks |
| `prune_search_root(root, query, …)` | one-shot prune |
| `render(res)` · `render_pruned(res)` | bundle → markdown |
| `get_code(root, relpath, symbol=None)` | one file or symbol (path-traversal hardened) |
| `ask(root, question, …)` · `render_ask(out)` | narrate + splice |
| `Store` · `ChunkMeta` | the storage layer and the read-side chunk record |
| `ChunkStrategy` · `Chunk` · `Symbol` · `FileResult` · `validate_partition` | the custom-chunker contract |
| `MegabrainError` · `IndexNotFound` · `EmptyIndex` · `MissingAPIKey` · `ProviderError` | the error taxonomy |

Imports are lazy and the package is `py.typed`. A custom chunker only has to satisfy one
hard rule: its chunks must form an **exact line partition** of the file.
