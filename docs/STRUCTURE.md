# Package structure

> **DONE.** All six moves landed in six commits, each with ruff and the full suite
> green: `chunkers/languages/` → `providers/` → `indexing/` → `ask/` →
> `knowledge/` + `chunkers/`. Zero behaviour change — `git mv` plus re-imports.
> The result, and the three places the code disagreed with this plan, are in §11.

282 files, 16 940 lines, and **every single module is at or under 100 lines** —
verified, because it is enforced (`tests/architecture/test_invariants.py`:
`MAX_FILE_LINES = 100`, `MAX_FUNC_LINES = 30`; the longest file in the engine is
exactly 100).

**So the file count is not the problem, and lowering it is not the goal.** A
16 940-line engine under a 100-line budget is ~200 files by arithmetic. The budget
is what keeps every file readable in one screen, and it stays.

The problem is that five packages drop 16–44 files at **one flat level**, and the
repo already contains the answer in `retrieval/`.

---

## 1. The rule

> **A package goes flat when every file answers the SAME question about a
> different subject. It needs subpackages when it contains different questions.**

Flat is not a failure state — it is correct for a registry:

| package | files | why flat is right |
|---|---|---|
| `contracts/` | 13 | one file per payload. The SDK's `types/` for the same reason |
| `usecases/` | 12 | one file per verb: `ask`, `search`, `grep`, `index` |
| `storage/` | 11 | one file per table |
| `transports/cli/commands/` | 11 | one file per command |
| `transports/http/routes/` | 9 | one file per route |
| `transports/mcp/` | 11 | one file per tool, plus the protocol |

Every one of those is "the same question, N subjects". Nesting them would add a
directory that means nothing.

`retrieval/` is the other shape, and it is the model to copy:

```
retrieval/
  search.py  intent.py  params.py  paths.py  state.py    the seams
  scoring/   pipeline.py  lane.py  lanes.py  context.py  evidence.py  _fusion.py  _space.py
  bundle/    assemble.py  floors.py  widen.py  _rank.py  _related.py  _anchors.py  _pins.py  _convert.py
  render/    markdown.py  _entries.py  _evidence.py  _fence.py  _lang.py
```

**Folder = a concern (a noun). The public file sits inside it, named after the
concern.** `scoring/pipeline.py`, `bundle/assemble.py`, `render/markdown.py`. That
is also `lib/` in the Anthropic SDK — `streaming/`, `tools/`, `credentials/`,
`bedrock/` — so the convention is not being invented here, it is being finished.

---

## 2. Measured state

| package | files | subdirs | LOC | verdict |
|---|---:|---:|---:|---|
| `ask/` | **44** | 0 | 2 784 | **worst — and it holds two different deliverables** |
| `chunkers/` | **31** | 0 | 1 710 | engine + 11 one-line language bindings, mixed |
| `knowledge/` | **24** | 0 | 1 574 | four unrelated concerns |
| `indexing/` | **21** | 0 | 1 660 | phases + edges + discovery, mixed |
| `providers/` | **16** | 1 | 1 007 | `chat/` is nested, the other two backends are not |
| `retrieval/` | 6 | 3 | 1 570 | ✅ the model |
| `transports/` | 1 | 4 | 1 900 | ✅ already nested |
| `contracts/` `usecases/` `storage/` `enrich/` `flows/` root | 9–13 | 0 | | ✅ registries, leave flat |

---

## 3. `ask/` — 44 files, and the real finding

`ask/` stopped being one thing. It now contains **the narrator** and **the edit-site
lane that `megabrain_grep` is built on**, and the second one arrived after the
package was laid out. Nothing in the directory says so: `_mentions.py` (a `grep`
lane) sorts alphabetically between `_litter.py` (citation cleanup) and
`_missing.py` (a narrator round).

```
ask/
  narrator.py  events.py  stream.py            the entry, and the stream contract

  prompt/      prompt.py  _rules.py  _opening.py  _candidates.py
               _chunkblocks.py  _block.py  _widen.py

  converse/    loop.py (_converse)  tools.py  _toolcall.py
               _flowctx.py  _missing.py  _filled.py  _admits.py

  citing/      citations.py  splice.py  _quote.py  _window.py
               _elide.py  _codeonly.py  _litter.py  _broken.py
               repair.py  _rescue.py

  checks/      grounded.py  pinned.py  callees.py  prune.py  surface.py

  agents/      fanout.py (agents.py)  _subagent.py  _pool.py

  sites/       sites.py  mentions.py  referenced.py  spans.py
               idents.py  spread.py  rows.py  words.py (_grepwords)
```

Two of those carry an argument beyond tidiness:

- **`citing/` is hard rule #5 made visible.** "The model cites; the engine splices
  verbatim code from disk" is the invariant that makes hallucinated code
  impossible, and the ten files that enforce it are currently scattered across
  the alphabet. As a folder, the rule has an address.
- **`sites/` is the `grep` deliverable, and it may not belong in `ask/` at all.**
  It shares the retrieval core with the narrator but shares no code path: no file
  in `sites/` calls a model. Splitting it out is what would let
  `test_retrieval_never_imports_an_llm` be extended to cover it, which today it
  cannot, because `ask/` legitimately imports a chat provider. **That is a
  follow-up, not part of the move** — it changes an import boundary, and this
  reorg changes none.

---

## 4. `chunkers/` — 31 files, 11 of which are one line of table

`c.py`, `cpp.py`, `csharp.py`, `java.py` are **13 lines each**; `go.py`, `php.py`,
`ruby.py`, `rust.py`, `typescript.py` are 18. They are "the shared tree-sitter
walk, bound to its language table" — and they sit beside the walk itself.

```
chunkers/
  model.py  units.py  cast.py                the contract, the seam, the engine
  _cast/       _split.py  _merge.py  _balance.py  _spans.py
               _breadcrumb.py  _signature.py
  treesitter/  chunker.py (treesitter.py)  _langspec.py  _names.py
               _nodes.py  _symbols.py  _calls.py
               specs/  core.py  c_family.py  optional.py
  languages/   python.py  _pysymbols.py  markdown.py
               c.py cpp.py csharp.py go.py java.py php.py ruby.py rust.py typescript.py
```

Eleven of the thirty-one files leave the top level and become one directory you
never open. That is the single largest reduction in visual noise available.

---

## 5. `indexing/` — 21 files

The phase split (`_plan` → `_embed` → `_write`) is a real pipeline that reads as
three private files, and the edge extractors are seven files that CLAUDE.md §5
already promised as `indexing/edges/<lang>.py` and never got.

```
indexing/
  indexer.py  discover.py  strategies.py          entry, walk, the language table
  passes/     plan.py  embed.py  write.py  resymbol.py
  edges/      python.py (edges.py)  typescript.py (ts_edges.py)
              _imports.py  _calls.py  _attrs.py  _reexports.py  _rebuild.py (_graph.py)
              pins.py
  ignore/     exclude.py  gitignore.py  unsupported.py
  registry/   builtin.py  _languages.py
```

## 6. `knowledge/` — 24 files

```
knowledge/
  build.py  node.py  views.py                     the graph, its node, the map
  graph/      weights.py  semantic.py  aliases.py
  clusters/   communities.py  labels.py  _naming.py  gods.py  surprises.py
  routes/     paths.py  route.py  story.py  carriers.py  tolls.py
  symbols/    links.py  locals.py  resolve.py  uses.py  usesites.py  source.py  snips.py
```

`clusters/` isolates the package's only LLM touch (`labels.py` + `_naming.py`),
which is worth being able to point at.

## 7. `providers/` — 16 files, and an asymmetry

`chat/` is already a folder. The HTTP transport, the embeddings codec and the
cache are not — they are mixed at the top level, so one backend has an address
and the other does not.

```
providers/
  embeddings/  embeddings.py  cache.py  _config.py  _wire.py  _width.py
               _batching.py  _budget.py  _replies.py  _oversize.py
  http/        http.py  _urllib.py  _retry.py  _stream.py  _local.py
  chat/        (unchanged)
```

---

## 8. What does NOT change

- **The 100-line budget.** It is what forces this granularity, and it is why every
  file is readable at a glance. A reorg that "fixed" the file count by merging
  files would trade a navigation problem for a reading problem.
- **`contracts/` and `usecases/`.** Flat is the correct shape for a registry
  (§1). Nesting them would be cargo-culting `retrieval/`.
- **`storage/`.** Flat *and* it has **130 external import sites** — the most
  imported package in the engine. Eleven files is within range; moving it would
  be the largest edit in the repo for no gain.
- **Any import boundary, any behaviour.** This is `git mv` plus re-imports.
  Public API, layering, and every invariant stay exactly as they are.

---

## 9. Execution

**One package per commit**, lint + full suite between each. Ordered by external
import sites, smallest first, so the mechanical part is validated on the cheapest
package before the largest one:

| # | package | files moved | external import sites |
|---|---|---:|---:|
| 1 | `chunkers/languages/` only | 11 | 56 (but the bindings are imported by 1 registry) |
| 2 | `providers/` | 14 | 54 |
| 3 | `indexing/` | 15 | 49 |
| 4 | `knowledge/` | 21 | 14 |
| 5 | `chunkers/` (rest) | 16 | 56 |
| 6 | `ask/` | 41 | 41 |

Rules for each commit:

- `git mv` **one file at a time** — no loop, no `sed -i` (global RULE 2). Roughly
  105 moves in total.
- Imports rewritten with `Edit`, one file at a time.
- Gates that must be green before the commit lands: `ruff check .`,
  `python -m pytest -q`, and the golden retrieval gate with its numbers quoted in
  the commit message — a reorg that silently moves R@1 is not a reorg.
- Re-export from the old module path only if something outside `src/` imports it;
  otherwise update the caller. A compatibility shim that nobody needs is a second
  name for one thing.

**Docs that go stale the moment this lands**, and must be in the same commit: the
tree in `ARCHITECTURE.md` §7, the package table in `AGENTS.md`, the phase map in
`CLAUDE.md`, and any `docs/` path reference.

---

## 10. What this does not fix

Worth stating so the reorg is not oversold — it buys navigation and nothing else:

- **`ask/sites/` sharing a package with a model-calling narrator.** The folder
  makes it visible; only moving it out of `ask/` would let the "no LLM" invariant
  cover it by test rather than by convention (§3).
- **The two citation grammars.** `[[k:lo-hi]]` (chunk index, `splice.py`) and
  `[[path:lo-hi]]` (file path, `_quote.py`) share bracket syntax and are
  disambiguated by whether the reference contains a `.` or `/`. Putting both in
  `citing/` puts the collision in one directory; it does not resolve it.
- **`_specs.py` / `_specs_c.py` / `_specs_more.py`.** Renamed to `core.py`,
  `c_family.py`, `optional.py` inside `specs/`, which is an improvement in
  naming, but the split itself is still "whatever fit under 100 lines" rather
  than a real grouping of languages.

---

## 11. What actually landed

| package | before | after (root) | subpackages |
|---|---:|---:|---|
| `ask/` | 44 | **4** | prompt · converse · citing · checks · agents · **sites** |
| `chunkers/` | 31 | **4** | `_cast` · treesitter (+ specs) · languages |
| `knowledge/` | 24 | **4** | graph · clusters · routes · symbols |
| `indexing/` | 21 | **9** | edges · passes |
| `providers/` | 16 | **2** | http · embeddings · chat |

No package now holds more than 13 modules, and every one still flat is a registry
where flat is correct (§1). 282 files, unchanged: nothing was merged.

**Three places the code disagreed with the plan above**, all of them corrections
the plan needed:

1. **`_local.py` stays at the root of `providers/`.** §7 put it in `http/`, but
   `chat/config.py` imports it too — it answers "is this endpoint on this
   machine", which both backends ask before deciding whether a missing API key is
   an error.
2. **No `ignore/` package in `indexing/`.** It would have held `unsupported.py`,
   which is the census of files NOTHING can chunk — not an exclusion rule. Three
   files do not earn a folder once the package is down to nine.
3. **`pins.py` went to `edges/`, not `registry/`.** It writes PIN_KIND edges, so
   it is an extractor. Grouping by "what it is" beat grouping by "when it runs".

**Traps worth knowing if you do this again**, each caught by the suite and not by
lint:

- Imports under `TYPE_CHECKING` are indented, so a grep for `^from` misses them.
  Three of them pointed at `indexing/edges.py`.
- Lazy imports inside function bodies, same reason: `from ._urllib import
  UrllibTransport` at `providers/embeddings/client.py:79` and
  `chat/openai_compat.py:80`.
- The `from <package> import <module>` form, which a rewriter matching
  `from X import <names>` will happily corrupt: `from megabrain.ask import _pool`.

The last three packages were moved by a written rewriter (relative → absolute →
map → relative, level recalculated per file) rather than by hand, at the repo
owner's explicit request — global RULE 2 bans mass rewrites, so it printed every
one of the 215 import lines it changed, and the suite was the net.
