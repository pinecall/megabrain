# megabrain — agent orientation

A local **code-intelligence engine**: one call returns all the code related to a
question, explained with the real code spliced in. It replaces minutes of
grep + Read + explore-agent crawling with one grounded answer.

- **What it does / how to use it** → [README.md](README.md) · [docs/GUIDE.md](docs/GUIDE.md)
- **The mental-model lane (`study` / `brief`)** → [docs/BRIEF.md](docs/BRIEF.md)
- **Every flag, tool, route and env var** → [docs/REFERENCE.md](docs/REFERENCE.md)
- **Task-oriented how-tos** → [docs/RECIPES.md](docs/RECIPES.md)
- **How it works, and why each choice is locked** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **What changed and when** → [CHANGELOG.md](CHANGELOG.md)

This file is orientation only: the rules you must not break, how to verify a
change, and where things live. It is not a changelog — don't add "SHIPPED"
notes here.

## Dogfood it — don't crawl files

The engine answers questions about any indexed repo, including itself:

```bash
megabrain index . --llm                    # once; incremental after (--llm adds the cards)
megabrain brief . "how does the brief avoid ranking twice"
megabrain ask   . "how does ask splice real code"
```

Over MCP, **three** tools — the surface carries only what megabrain alone can do, since
the host already has Read, Grep and an editor: `megabrain_ask` (the whole flow behind a
question or a change, narrated, and the narrator OPENS what retrieval missed) ·
`megabrain_search` (the map, and the docs) · `megabrain_index`. Prefer these over
grep/Read chains. It was briefly five: `megabrain_code` and `megabrain_replace` were
measured across five tasks in three languages and removed — the value was the opening,
which now belongs to `ask`, and the edit machinery kept being discarded by its readers.

## Hard rules — locked by experimental data, do not violate

1. **No LLM in the retrieval path.** Query-time LLM calls sit *above* retrieval and
   all fail open: `ask` (narrator), the optional `search --rerank` judge lane, one
   cached `graph` community-label call. Two passes run a model at **index** time
   instead, each gated by a deterministic oracle that decides whether the output may
   be stored at all: `forge` (partition oracle) and **`study`** (card oracle — see
   [docs/BRIEF.md](docs/BRIEF.md)). `brief` itself makes **zero** model calls.
2. **Completeness beats ordering.** Never merge a change that lowers golden
   `bundle_full` (currently **1.00**).
3. **The graph never ranks.** Import/call edges supply candidates and map
   annotations only — PageRank-as-ranking was rejected (Acc@1 0.91 → 0.73).
4. **Chunks are a line partition.** `validate_partition` must stay clean: no
   gaps, no overlaps.
5. **`ask` shows real code only.** The model cites `[[k]]`; the engine splices
   verbatim from disk. Never let the model emit code.

## Gates — run BOTH after any change under `src/megabrain/`

```bash
ruff check .            # not optional: skipping it shipped 3 releases with CI red
python3 -m pytest -q    # full OFFLINE suite (no key, no network) — what CI runs
```

For retrieval changes also run the golden gates (they need a local indexed
corpus kept out of this repo): `python3 tests/test_engine_golden.py`
(R@1 ≥ 0.85, **bundle_full ≥ 0.90**), `tests/test_multi_repo.py`,
`tests/test_scale.py`. Current bar: R@1 0.86 · bundle_full 1.00 · p50 ~10 ms.

Two traps that bite repeatedly:

- A golden that fingerprints this repo's own source breaks on **every** version
  bump — regenerate with `RESET_CAST=1 python3 -m pytest tests/test_cast_unification.py`.
- **Windows is a first-class CI target.** Repo-relative paths are POSIX
  everywhere (`Path.as_posix()`, never `str(path)`); pass `encoding="utf-8"`
  explicitly to every `read_text`/`write_text` or cp1252 silently corrupts
  non-ASCII.

## Layout

The tree mirrors the pipeline; full detail in [ARCHITECTURE.md](ARCHITECTURE.md) §7.

| package | role |
|---|---|
| `chunkers/` | content → chunks behind one `FileResult` contract. `cast` is the shared engine; `python` (stdlib ast), `treesitter` (+`LangSpec`: TS/JS, Ruby, Go, Rust, PHP), `php` (legacy shape-router), `markdown` (no-LLM) |
| `indexing/` | `indexer` (incremental walk + 60 s auto-refresh) · `strategies` (ext → strategy registry, the OCP extension point) · `graph` (import/call edges) · `ignore` |
| `retrieval/` | **no LLM in here.** `scoring` (lane pipeline) · `bundle` (rank/tier/prune) · `render` · `state` (warm `SearchState`) · `issue` · `bm25` · `files` · `rerank` (the one opt-in LLM lane) |
| `ask/` | `narrator` (walkthrough + `splice`) · `agents` (classifier → planner → parallel sub-agents → synthesizer, the event stream drives every surface) · `repair` (a citation that resolved to nothing, re-asked) |
| `atlas/` | **the mental map** — `author` (the ONLY module here that calls a model, at *index* time) · `oracle` (accepts/rejects a card, no LLM) · `_plan` (`CARD_SCHEMA` + the cache key) · `brief` (query time, 0 LLM: the bundle's own file list, re-presented) · `render` |
| `enrich/` | `Bundle → Bundle`, opt-in, fail-open to the input. `rerank` = the judge lane: the model returns IDS, never code |
| `storage/` | `store` (SQLite, the ONLY package that writes SQL) · `_cards` (the study cards — no vector column: cards never rank) · `_flows` · `locate` (`resolve_root` + `INDEX_FILE`, the layout in one line) |
| `providers/` | model APIs: chat routing, `claude` (Agent SDK), `embeddings` |
| `forge/` | `coverage` (LLM-written chunkers, partition-gated, trust-installed) · `specialize`+`ab_gate` (measure-only, NO LLM) |
| `graph.py` | the knowledge graph (numpy only) |
| `usecases/` | the use-case layer — **one file per verb**; every transport maps its args to these. `build` composes `index` + `study` behind `llm=True`, so no surface can disagree about what "index with the LLM" means |
| `transports/` | `cli` (one module per verb) · `mcp` (three tools; `inputSchema` GENERATED from `contracts/tools.py`) · `http` (studio + JSON API, `ui/` is the built studio bundle) · `install` (`megabrain install` — the six-assistant MCP registration table) |

Runnable examples live in their own repo, `~/megabrain-examples`.

## Releases — maintainer only, never without explicit approval

1. Bump `src/megabrain/__init__.py:__version__` and add a `## X.Y.Z — title`
   section to `CHANGELOG.md` (that section becomes the GitHub release notes).
   A breaking change to a public contract (CLI/MCP/HTTP) is a MINOR bump in 0.x.
2. Run both gates locally, then `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. `release.yml` takes over. It **cannot publish something broken**: `publish`
   needs `guard` (the tag must equal `__version__`) plus `gates` (this repo's
   `ci.yml`, invoked through `workflow_call`, so lint and the full
   OS × Python matrix run against the tagged commit). Publishing is tag-only
   and goes to PyPI via Trusted Publishing (OIDC, no token).

To rehearse the workflow without burning a version:
`gh workflow run release.yml --ref master` — everything runs, `publish` skips.

**Gotcha:** a push that touches `.github/workflows/*` is rejected by the default
HTTPS OAuth token (no `workflow` scope). Push those with an account that has it,
or `gh auth refresh -s workflow`.

## Contributing

Non-trivial work goes through a branch and a PR (`gh pr create --fill`); merge
only when CI is green. Keep `master` green — the two gate commands above catch
almost everything CI would.

## The live demo runs THIS package

`bernardocastro.dev/megabrain/demo` is the real `megabrain studio` from PyPI
(`--readonly --rate-limit 30 --trust-proxy`) behind nginx — no custom backend or
frontend. So a demo-visible bug is almost always an engine bug, fixed here and
shipped by a release. Its deploy lives in the `bernardocastro.dev` repo
(`services/megabrain/`) and ends in a 25-assertion smoke test whose every check
comes from a real outage — see that directory's README.
