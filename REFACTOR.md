# REFACTOR — the gap between "works" and 10/10

Findings from a full read of `src/megabrain/` + `studio/src/` (335 files, 21,383
lines, 2026-07-28). Everything below passes the gates today; that is exactly why
it is written down — a green suite does not argue with a design error. Ordered by
severity. Each item names the files and the fix; none changes public behaviour,
so every one lands with the golden gate byte-identical.

Rules referenced: **[R4]** no duplicated logic / reuse before rewriting ·
**[OCP]** extend, don't modify · **[LAY]** dependency arrows point down only.

---

## P0 — design errors (wrong even though they work)

### 1. `grep/` reaches into `ask/`'s privates — a layering inversion [LAY]

`grep` is the package whose whole identity is "no model, its own deliverable" —
it earned its own folder precisely to escape `ask/`. Yet its verb still imports
**four private internals of the package it escaped**:

```
grep/grep.py:36   from ..ask.converse.loop import answered
grep/grep.py:38   from ..ask.prompt._candidates import candidates_of
grep/grep.py:39   from ..ask.prompt._chunkblocks import chunk_blocks
grep/grep.py:89   from ..ask.ask import _narrator          ← a PRIVATE function
grep/rows.py:18   from ..ask.checks.surface import import_surface
```

Two siblings at L4 with an arrow between them, three of the five targets
underscore-private. `ask` cannot rename `_narrator` or reshape its prompt
internals without silently breaking `grep` — the exact drift the package split
was bought to prevent. The architecture test only fences `grep/`'s **lanes**
(`grep.grep` is exempt by name), so this cannot even be caught.

**Fix:** promote the three shared pieces to a neutral home they both sit above:

- `_narrator(root)` → `providers/chat/for_repo.py::narrator_for(root)` — it is
  provider resolution, not narration; `graph/clusters/labels.py` re-implements
  the same 4 lines a third time (see P1-4).
- `candidates_of` + `chunk_blocks` (+ `answered`) → they are "turn a Bundle into
  a prompt over candidates", used by two features. Either `search/render/` grows
  a `prompt.py`, or a small `promptkit/` at L4 that both import. The measured
  balance (`MAX_BODIES = 8`) is the shared asset; today it is shared by reaching
  into a sibling's underscore modules.
- `import_surface` → it reads the Store and produces metadata; it belongs beside
  the symbol table (`storage/` helper or `grep/` itself — `ask` only uses it via
  `checks/`, which can import from the new home).

Then extend `test_grep_never_imports_a_model` to assert `grep/` (verb included)
imports nothing from `megabrain.ask` at all.

### 2. One computation, three implementations: "sha256 of a file on disk" [R4]

```
flows/freshness.py:sha_of          read_text(errors="replace") → sha256, "" on OSError
usecases/freshness.py:_sha         identical, re-written
usecases/get.py:_changed_on_disk   identical, inlined a third time
```

`flows/freshness.py`'s docstring says "the same content hash indexing uses, so
the two agree by construction" — and then two more copies exist that agree only
by coincidence. `indexing/passes/plan.py:1135` hashes the same way a fourth time
(justifiable: it hashes an already-read string), but the three *file* hashers
are one function. **Fix:** `sha_of(path)` lives once (it already has the best
home and docstring in `flows/freshness.py`; move it to `storage/` or `_utils`
so `usecases/` doesn't import a feature package) and the other two call it. A
future change to the read policy (`errors=`, encoding) currently has three
places to miss.

### 3. "Resolve a bare name to its unique definition" exists three times [R4]

```
ask/checks/callees.py:_definition_of    find(name), filter kinds, unique-or-None
ask/converse/_missing.py:_definition    find(name), unique-or-None
grep/referenced.py:_resolved            find(name), span filter, unique-or-None
```

All three implement the same safety rule ("a jump that could land anywhere is
worse than no jump") with slightly different filters — `callees` excludes
containers and headings, `_missing` excludes nothing, `referenced` excludes
headings and wide spans. The differences are undocumented, so nobody can say
whether `_missing` serving a `class` body (which `callees` would refuse) is a
decision or an accident. **Fix:** one
`storage/_symbols.py::unique_definition(name, *, exclude_kinds, max_span, prefer_files)`
with the three call sites passing their policy explicitly. The policy deltas
become visible parameters instead of three drifting copies.

### 4. `grep` fabricates a Bundle and suppresses the type error

```python
# grep/grep.py:95
blocks = chunk_blocks(candidates_of({**bundle, "flows": []}))  # type: ignore[typeddict-item]
```

A `type: ignore` on a TypedDict construction is the contract saying "this shape
is wrong" and being overruled. The real problem: `candidates_of` demands the
narrator's flow-carrying Bundle while `search()` returns one without `flows`
populated the way `ask` attaches them. **Fix:** `candidates_of` should accept
the search Bundle (read `bundle.get("flows", [])`) — one `.get` deletes the
fake construction and the suppression. This falls out of P0-1's promotion.

---

## P1 — duplication and dead weight

### 5. Dead code inventory (verified: zero callers)

| what | where | why it's dead |
|---|---|---|
| `operations()` + `_OPERATIONS` | `transports/mcp/_payload.py:40-63` | served `megabrain_replace`, removed with it. Its `Missing` message still tells agents to send edit batches no tool accepts |
| `limit()` + `BRIEF_LIMIT/BRIEF_MAX` | `transports/mcp/arguments.py:56-60` | no surviving tool takes `limit`; also duplicated as `_BRIEF_LIMIT/_BRIEF_MAX` in `transports/http/routes/query.py:23-24` (equally unused) |
| `contracts/prune.py` — `PruneResult`, `NoiseSpan`, `RelatedDoc`, `RelatedTest` | whole module | no producer in v3 (`--prune` was not ported). Exported from `contracts/__init__` as if live |
| `MAX_CANDIDATES = 40` | `ask/narrator.py:44` | shadow of the real one in `prompt/_candidates.py`; never read in `narrator.py` |
| `Running = "dict[Future[str], Task]"` | `ask/agents/_pool.py:26` | a string constant pretending to be a type alias; never used |
| `_PROSE_REF`, `_ANY_BRACKETED` | `ask/citing/repair.py:43-46` | exact copies of `_broken.py`'s; `repair` calls `broken_references` and never touches its own copies |
| `EventType` Literal | `ask/events.py` | defined, unexported, unused; `EVENT_TYPES` duplicates the list by hand. Keep one and derive the other (`get_args`) |
| `studio/src/search.ts`, `studio/src/files.ts` | whole modules | superseded by `views/search.ts` / `views/files.ts`; `main.ts` imports only the `views/` pair. Dead source esbuild still ships |

Delete all of it. Dead code with a docstring reads as live; every future reader
pays the read.

### 6. The judge-provider resolution is pasted twice in `search.py` [R4]

`search/search.py:_expanded` (L268-269) and `_judged` (L292-293) both do
`proj = load_project(root); judge_provider(proj.rerank_model, provider=proj.chat_provider)`.
Two sites already drifted once (the `provider=` param was added to both by
hand). **Fix:** one `_judge_of(root)` helper — or fold into P0-1's
`providers/chat/for_repo.py` (`judge_for(root)` beside `narrator_for(root)`),
which also absorbs the third copy in `graph/clusters/labels.py:_ask`.

### 7. `Store` takes `Path`, callers pass `str`, ignores paper over it

`storage/store.py:37` declares `repo_root: Path`; `graph/build.py:73` and
`graph/clusters/labels.py:32` call `Store(root)` with `str` under
`# type: ignore[arg-type]`, because the whole `graph/` package threads
`root: str` (from `load_graph(str(root))` upward). One package speaking `str`
in a codebase that is `Path` everywhere else is the incoherence; the ignores
are the symptom. **Fix:** `Store.__init__(repo_root: Path | str)` (one-line
`Path(repo_root)` it already does) **and** migrate `graph/`'s signatures to
`Path` so the `str(root)` casts at every `graph_map`/`graph_node` call site
disappear too.

---

## P2 — naming, cohesion, small smells

### 8. `_toolless.py` owns the always-used request builder

`ask/converse/_toolless.py` is named for the exceptional case but exports
`RequestBody` — the class **every** conversation routes through
(`loop.py:body = RequestBody(_body)`). A reader looking for "who builds the
request" will not open a file called "toolless". **Fix:** `RequestBody` →
`_body.py` (or into `loop.py`, it's 25 lines); `_toolless.py` keeps the
detection (`rejects_tools`, `without_tools`) it is named for.

### 9. `ClaudeProvider._chosen` (method) vs `chosen` (ctor param) — same word, two meanings

`providers/chat/claude.py`: the constructor's `chosen: bool | None` is "the
opt-in, already resolved"; the private method `_chosen(requested)` is "pick the
model name". Adjacent lines, unrelated concepts, one word. Rename the method
`_model_for(requested)`.

### 10. Two `_missing.py`, opposite meanings

`ask/converse/_missing.py` (the bodies an answer lacked) and
`transports/mcp/_missing.py` (a required-argument exception). Different
packages, so imports are unambiguous — but a grep for `_missing` returns both
and the names teach nothing. The MCP one is one exception class; fold it into
`arguments.py` (its only real consumer surface) and delete the module.

### 11. `enrich/rerank.py` cosmetics

Line 26-29: `MAX_TOKENS = 300` followed by two stray blank lines (the scar of
the old `judge_provider` body). `ruff format` would catch it if formatting ran
in the gate; it doesn't — `scripts/format` exists but `scripts/lint` never
checks formatting. Consider `ruff format --check` in the lint gate so scars
like this can't accumulate.

### 12. `graph/routes/carriers.py` — the `((two, one), (one, two))` dance, twice

`hop_symbols` and `_pair` both iterate the direction pairs with the same
inverted-tuple idiom and no shared name for it. Minor, but a
`_directions(one, two)` helper (or a comment naming the pattern once) would
stop the next reader from re-deriving why the tuples are backwards.

### 13. Studio: `judge.ts` and `scope.ts` at root, their consumers under `views/`

After deleting the dead root `search.ts`/`files.ts` (P1-5), the remaining root
modules split into "framework" (`dom`, `api`, `contracts`, `icons`, `theme`,
`markdown`) and "widgets used by views" (`judge`, `scope`, `suggestions`). The
second group belongs in `views/` or a `widgets/` folder — directory coherence,
same argument `docs/STRUCTURE.md` §1 makes for the Python tree.

---

## Explicitly NOT proposed

- **Merging small files.** The 100-line budget is the architecture, not a smell.
- **A `core/`+`features/` re-layout.** `docs/DOMAINS.md` §5's objection stands.
- **Touching any tuned constant or prompt.** Phase 17 territory, pre-registered
  hypotheses only.
- **De-duplicating the studio's `contracts.ts` mirror.** Hand-mirrored is the
  documented decision; a generator is a second build step to keep alive.

## Suggested order

1. P1-5 dead-code sweep (pure deletion, instant win, shrinks every later diff)
2. P0-1 + P1-6 together (the `providers/chat/for_repo.py` home solves both, and
   P0-4 falls out) — then tighten the grep architecture test
3. P0-2, P0-3 (the two R4 consolidations, one PR each, tests first)
4. P1-7 (`Path | str` + `graph/` migration)
5. P2 batch

Every step: test first, RED, gates green, golden numbers in the commit message
where retrieval-adjacent (P0-1 touches prompt assembly for `ask`/`grep` — run it).
