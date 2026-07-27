# Proposal: package by DOMAIN, not by layer

> Status: **the small version LANDED, the full split did not.** `retrieval/ → search/`,
> `knowledge/ → graph/`, `ask/sites/ → grep/`, and then each verb moved in beside its own
> logic — so §1's complaint no longer describes the tree (`docs/STRUCTURE.md` §12 records
> what happened, and the table in §1 below is kept as the diagnosis that motivated it).
> What is still only proposed is §2's `core/` + `features/` + `transports/` layout: the
> objection in §5 — that the layer numbering is what the executable invariants name, and
> that the features are not peers — was never answered, only outweighed for the cheap half.

## 1. The complaint, stated precisely

The product does four things — **ask**, **grep**, **search**, **graph** (plus
**index**, which makes the other four possible). Open `src/megabrain/` and three
of the five are not there:

| the feature | where its logic actually lives | called |
|---|---|---|
| `ask` | `ask/` minus `sites/` | ✅ ask |
| **`grep`** | **`ask/sites/`** — 9 files inside another feature | ❌ |
| **`search`** | **`retrieval/`** (29 files) + `enrich/` | ❌ |
| **`graph`** | **`knowledge/`** (28 files) | ❌ |
| `index` | `indexing/` + `chunkers/` | ~ |

Each verb also has a one-file entry in `usecases/` and a command in
`transports/cli/commands/`, so the pieces of one feature are spread across three
places under three different names.

The worst of it is `grep`. It is a separate deliverable — **no file in it calls a
model** — living inside the one package whose entire job is calling a model.
`docs/STRUCTURE.md §3` already flags this and defers it.

## 2. The proposal

```
src/megabrain/
  core/                    what every feature needs and none of them owns
    storage/     13        SQLite; the only package that writes SQL
    chunkers/    35        content → chunks (cast, treesitter, languages)
    providers/   24        embeddings · http · chat
    contracts/   13        every cross-boundary payload, TypedDict only
    _types _arrays _errors project …

  features/
    search/      38        the retrieval engine AND its verb
                           scoring · bundle · render · enrich (the judge lane)
    grep/        10        WHERE TO EDIT — no model, ever
                           sites · mentions · referenced · spans · idents · spread
    ask/         42        NARRATE — the only query-time LLM
                           prompt · converse · citing · checks · agents · flows
    graph/       28        the import/call graph and what you ask of it
                           graph · clusters · routes · symbols
    index/       23        BUILD — passes · edges · discover · strategies

  transports/    49        cli · mcp · http · install
```

Every feature folder holds **its verb, its logic, and its own tests' subject** —
`features/grep/grep.py` is what `usecases/grep.py` is today, with the eight lanes
beside it instead of two packages away.

## 3. What this buys

- **`grep` becomes a thing.** Nine files that share no code path with the
  narrator stop living inside it, and the "no model" rule becomes a property of a
  DIRECTORY, which a test can assert (§5).
- **The name is the feature.** Nobody has to learn that `retrieval` means search
  and `knowledge` means graph. Today a new reader greps for "grep" and finds
  `usecases/grep.py`, which imports from `ask/`.
- **A feature is one place.** Adding `--why` to grep today touches
  `usecases/grep.py`, `ask/sites/words.py`, `contracts/tools.py` and
  `transports/{cli,mcp}`. Three of those five would collapse into one folder.
- **`core/` states the split that already exists.** `storage`, `chunkers`,
  `providers` and `contracts` are used by everything and own no feature; that is
  currently something you infer.

## 4. What it costs — and the one real objection

**The layering is enforced by tests that name packages.** `tests/architecture`
asserts that `retrieval/` imports no LLM and that only `storage/` writes SQL.
Those tests are the reason the rules held while five packages were reorganised
today. Move the packages and every one of them has to be rewritten — not deleted,
rewritten, and a rule that is rewritten under pressure is a rule that can quietly
weaken.

**Features are not peers, and the tree would imply they are.** `ask` and `grep`
both build on `search`; `search` builds on `core`. So `features/ask` imports
`features/search`, which is a dependency between siblings — the exact thing the
current L0→L5 numbering makes visible and a flat `features/` hides. Mitigation:
keep the layer numbers in the docstrings and add a test that the arrow only
points one way (§5), rather than pretending the four are independent.

**It is ~180 files moved**, on top of the ~105 moved today, with the same
mechanical risk profile: `git mv` plus re-imports, no behaviour change.

## 5. The tests that would have to come with it

A reorg that weakens the invariants is not worth doing, so these are part of the
work, not a follow-up:

```python
def test_grep_never_imports_a_model():
    """The whole reason `grep` earns its own folder: it answers in ~50 ms
    because nothing in it can call out. Today this cannot be asserted —
    `ask/` legitimately imports a chat provider, and grep lives inside it."""
    assert not imports_under("features/grep", "core.providers.chat")

def test_a_feature_imports_only_core_and_search():
    """`ask` may build on `search`; nothing may build on `ask`. Flat folders
    lose the ordering the L0-L5 numbering shows, so it gets asserted instead."""
```

That first test is the strongest argument for the whole proposal: **there is a
rule we cannot express today because the code is in the wrong folder.**

## 6. Smaller alternative, if the full move is too much

Two renames and one extraction get most of the value for a fifth of the risk:

```
retrieval/  →  search/          the name becomes the feature
knowledge/  →  graph/           idem
ask/sites/  →  grep/            grep leaves the LLM package
```

~40 files instead of ~180, `core/` and `features/` never appear, every
architecture test keeps working with a renamed string, and `test_grep_never_
imports_a_model` becomes possible immediately.

The remaining awkwardness — `usecases/` holding a verb per file away from its
logic — stays. That is the part the full proposal fixes and this one does not.

## 7. Recommendation

**Do §6 now, and §2 only if the seam still hurts afterwards.**

The value the complaint is pointing at is concentrated in three names and one
misplaced package, and §6 buys those without rewriting the invariants that just
proved their worth. §2's `core/` + `features/` is the right end state for a
codebase where features are added often; this one adds them rarely and changes
their internals constantly, which is the shape layering serves better.
