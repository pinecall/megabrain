# megabrain — agent orientation

A local **code-intelligence engine**: one call returns all the code related to a
question, explained with the real code spliced in. It replaces minutes of
grep + Read + explore-agent crawling with one grounded answer.

- **What it does / how to use it** → [README.md](README.md) · [docs/GUIDE.md](docs/GUIDE.md)
- **Every flag, tool, route and env var** → [docs/REFERENCE.md](docs/REFERENCE.md)
- **The token measurements, reproducible** → [docs/BENCHMARKS.md](docs/BENCHMARKS.md)
- **The tree, and the packaging argument behind it** → [docs/STRUCTURE.md](docs/STRUCTURE.md) · [docs/DOMAINS.md](docs/DOMAINS.md)
- **Task-oriented how-tos** → [docs/RECIPES.md](docs/RECIPES.md)
- **How it works, and why each choice is locked** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **Known design debt, prioritized with file:line** → [REFACTOR.md](REFACTOR.md) —
  read it BEFORE "improving" something: it also lists what looks like a smell and
  is a decision
- **What changed and when** → [CHANGELOG.md](CHANGELOG.md)

This file is orientation only: the rules you must not break, how to verify a
change, and where things live. It is not a changelog — don't add "SHIPPED"
notes here.

## Dogfood it — don't crawl files

The engine answers questions about any indexed repo, including itself:

```bash
megabrain index .                                       # once; incremental after
megabrain ask  "how does ask splice real code" .        # the question FIRST, the path second
megabrain grep "add a lane to the scoring pipeline" .   # where to edit, no model
```

Over MCP, **four** tools. Three share one retrieval core and differ by DELIVERABLE,
because "find me this code" is three jobs: `megabrain_grep` (about to EDIT — files,
symbols, exact line ranges, no code, because your editor opens the file anyway) ·
`megabrain_ask` (UNDERSTAND a mechanism, or copy a pattern out of another repo — narrated
with the real code spliced in) · `megabrain_search` (the DOCS, or the map — chunks with no
model, and never the input for an edit: it ranks what EXISTS, so a missing call is what it
cannot show you). Plus `megabrain_index`. `megabrain_code`/`megabrain_replace` were
measured across five tasks in three languages and removed; `grep` is the half that
worked.

## Hard rules — locked by experimental data, do not violate

1. **No LLM in the retrieval path.** Query-time model calls sit *above* retrieval and
   all fail open: `ask` (narrator) and the opt-in `enrich/` lanes (`rerank` for order,
   `expand` for recall). Exactly one call happens outside a query — the cached `graph`
   community-label call — and it cannot reach retrieval either. **A test walks the
   imports**: nothing under `search/` or `grep/` may import `providers.chat` or
   `enrich/`, and only the two verb modules are exempt, because composing a lane the
   caller asked for is their job.
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
uv sync --group dev     # once: the gates are a PEP 735 dev group, not an extra
./scripts/lint          # ruff + mypy + pyright + the architecture invariants
./scripts/test          # the full OFFLINE suite (no key, no network) — what CI runs
```

`./scripts/lint` is the whole static gate and CI runs THAT file, not inline steps —
running only `ruff` shipped three releases with CI red. It prepends `.venv/bin` to
`PATH` on purpose: `.venv/bin/pyright` resolves `python` to the *global* interpreter and
sees a different numpy, so the two spellings disagreed (0 errors against 8) and the
script's answer is the one CI reproduces.

For any change under `search/`, `chunkers/` or `providers/embeddings/`, also run the
**golden gate**. Its corpus is private, so the test SKIPS loudly rather than passing
vacuously:

```bash
MEGABRAIN_GOLDEN=/path/to/golden.json MEGABRAIN_GOLDEN_REPO=/path/to/corpus \
  ./scripts/test tests/golden
```

Current bar: **R@1 ≥ 0.86 · bundle_full = 1.00 · p50 ~10 ms**. Put the actual three
numbers in the commit message, not "still passes" — that is what makes a regression
visible in `git log` even if nobody re-ran the gate at merge time.

Two traps that bite repeatedly:

- **A green unit test proves nothing about code that talks to something external.**
  Every bug the domain audit found there had a passing test beside it, because the
  fixture and the bug were written from the same wrong assumption. Where behaviour
  meets a real corpus, endpoint or database, the test has to meet one too.
- **Windows is a first-class CI target.** Repo-relative paths are POSIX
  everywhere (`Path.as_posix()`, never `str(path)`); pass `encoding="utf-8"`
  explicitly to every `read_text`/`write_text` or cp1252 silently corrupts
  non-ASCII.

## Layout

The tree mirrors the pipeline; full detail in [ARCHITECTURE.md](ARCHITECTURE.md) §7.

| package | role |
|---|---|
| `chunkers/` | content → chunks behind one `FileResult` contract. `cast` is the shared engine · `_cast/` its six steps · `treesitter/` ONE walk parameterised by a `LangSpec` (+ `specs/`) · `languages/` eleven bindings of 13–18 lines each, plus `python` (stdlib ast) and `markdown` (no-LLM) |
| `indexing/` | `indexer` (incremental by content hash — **no auto-refresh**, at query time or otherwise) · `strategies` (ext → registry, the OCP point, `EDGE_SCHEMA`) · `passes/` plan→embed→write→resymbol · `edges/` per-language extractors + `pins` · `_gitignore` |
| `search/` | **no LLM in here**, enforced by a test. `scoring/` (the lane pipeline) · `bundle/` (rank, tier, the two recall floors) · `render/` · `state` (warm `SearchState`) · `paths` (the path vocabulary) |
| `graph/` | the graph (candidates + annotations, **never ranking**). `weights`/`semantic`/`aliases` — what an edge weighs · `clusters/` communities and their labels — *the package's only LLM touch* · `routes/` BFS questions asked at query time · `symbols/` go-to-definition and its inverse |
| `converse/` | the SHARED model loop, neutral ground between the verbs: `loop` (the `open_file` conversation) · `candidates`/`chunkblocks` (what the model is shown) · `backend` (which model the repo chose) — imports neither `ask/` nor `grep/`, enforced |
| `ask/` | the query-time LLM layer. `narrator` · `prompt/` (8 bodies + a map) · `citing/` (**rule 5**: the model cites, the engine splices) · `checks/` (deterministic, no model) · `agents/` (fan-out) · `ask.py` (the verb) |
| `grep/` | **`megabrain_grep`** — its own package so "it calls no model" is a *test*: the lanes (`sites` `mentions` `referenced` `spans` `idents` `spread` `rows` `surface` `_prompt`) cannot call out, and the opt-in `why` lives above them in `grep.py`; it never imports `ask/` at all — the shared pieces live in `converse/` |
| `forge/` | strategies the machine writes or measures: `detect` census → the model writes a `parse` (coverage) → the ORACLE accepts/repairs → sha-trust-gated install (`indexing/trust.py`); `ab_gate`/`specialize` = the no-model empirical judge for hand-written strategies |
| `flows/` | the cached-walkthrough lane: `cache` · `serve` · `match` · `covers` · `freshness` · `chrome`. The read path is cosine + file hashes only |
| `enrich/` | `Bundle → Bundle`, opt-in, fail-open to the input. `rerank` = the judge (the model returns IDS, never code, and never drops a file) · `expand` = the widener (the model names identifiers, the SYMBOL TABLE resolves them) |
| `storage/` | `store` (SQLite, the ONLY package that writes SQL) · one module per table · `_flows` · `locate` (`resolve_root` + `INDEX_FILE`, the layout in one line) |
| `providers/` | model APIs, one folder per backend: `http/` (the shared transport) · `embeddings/` (Layer 2 — retrieval depends on it) · `chat/` (Layer 4 — nothing under `search/` may import it; TWO backends behind `router.resolve()`: the OpenAI-compatible endpoint and the opt-in Claude Agent SDK, switched by `megabrain.json` `models.provider` / `MEGABRAIN_CHAT_PROVIDER`, and the switch moves EVERY model lane at once) · `_local` (asked by both) |
| `usecases/` | the verbs that belong to no single feature (`get` `scan` `repos` `freshness` `starters`), plus a re-export of the four that live in their own packages — so every transport still has one import to reach any verb |
| `transports/` | `cli` (one module per verb) · `mcp` (four tools; `inputSchema` GENERATED from `contracts/tools.py`) · `http` (studio + JSON API, `ui/` is the built studio bundle) · `install` (`megabrain install` — the six-assistant MCP registration table) |

Runnable examples live in their own repo, `~/megabrain-examples`.

## Releases — maintainer only, never without explicit approval

⚠️ **Version reality, verify against the registry, not against files**: PyPI's
latest published is **0.18.6** and so is the last git tag. This branch declares
`1.0.0` in `_version.py` and the README — deliberate, and **unreleased**: work
continues here until the maintainer says ship. Never reset the number down; PyPI
versions are permanent.

1. Bump `src/megabrain/_version.py:__version__` (the ONE place; `pyproject.toml` reads it
   from there) and add a `## X.Y.Z — title`
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
(`--readonly --rate-limit 30`) behind nginx — no custom backend or
frontend. So a demo-visible bug is almost always an engine bug, fixed here and
shipped by a release. Its deploy lives in the `bernardocastro.dev` repo
(`services/megabrain/`) and ends in a 25-assertion smoke test whose every check
comes from a real outage — see that directory's README.
