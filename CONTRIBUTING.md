# Contributing to megabrain

## Dev setup

```bash
git clone https://github.com/bernatch22/megabrain && cd megabrain
uv sync --group dev            # or: pip install -e ".[languages]" --group dev
./scripts/lint                 # ruff + mypy + pyright + the architecture invariants
./scripts/test                 # the full suite — fully offline, no key, no network
```

The gates live in a **PEP 735 dependency group**, not an extra: they are not part of
what anyone installs megabrain *for*, and an extra would advertise them on PyPI as if
they were. `./scripts/lint` prepends `.venv/bin` to `PATH` deliberately — a mixture of
a global `ruff` and a venv `mypy` made the gate depend on whose machine ran it.

Both scripts are what CI runs. `./scripts/test` also has to pass on **3 OS × Python
3.10–3.13**, so two things are not optional: repo-relative paths are POSIX everywhere
(`Path.as_posix()`, never `str(path)`), and every `read_text`/`write_text` passes
`encoding="utf-8"` explicitly, or cp1252 silently corrupts non-ASCII on Windows.

## The rules that are locked by experimental data

Each was decided by a measured experiment ([ARCHITECTURE.md](ARCHITECTURE.md) §8). Don't
send a PR that violates one without new evidence — and note that three of them are
enforced by tests in `tests/architecture/`, so a violation is a red suite, not a review
argument:

1. **No LLM in the retrieval path.** LLM pruning was tested four ways and every variant
   cost completeness or added seconds for no recall gain. The model calls are `ask`
   (narration), the opt-in `enrich/` lanes (`rerank` for order, `expand` for recall) and
   one cached graph-labelling call at index time — all fail-open. *Enforced:* nothing
   under `search/` or `grep/` may import `providers.chat` or `enrich/`.
2. **Completeness beats ordering.** A change must not lower golden `bundle_full`
   (currently **1.00**). A ranking win that costs recall is rejected.
3. **The graph never ranks.** Import/call edges supply candidates and map annotations
   only — PageRank-as-ranking measurably hurt (Acc@1 0.91 → 0.73).
4. **Chunks are a line partition.** Every chunker keeps `validate_partition` clean: no
   gaps, no overlaps, full file coverage.
5. **`ask` shows real code only.** The model cites `[[k]]` spans; the engine splices
   verbatim code from disk. Never let the model emit code.

Also enforced, and worth knowing before your diff bounces: **SQL only inside
`storage/`**, **no `assert` in shipped code** (`python -O` deletes it — raise instead),
**no `asyncio.run` outside `transports/http/`**, and **100 lines per file / 30 per
function**, checked per module.

## Testing

`./scripts/test` is offline and covers the chunkers (partition guarantees per language),
retrieval, indexing, storage, the providers against fake transports, the public surface
and the payload contracts. **Write the test first and watch it fail** — a test that
passes the first time it runs has not been shown to be able to fail.

The end-to-end retrieval gate (a golden set over a private corpus) runs maintainer-side:

```bash
MEGABRAIN_GOLDEN=… MEGABRAIN_GOLDEN_REPO=… ./scripts/test tests/golden
```

It **skips loudly** without those, because a green check that measured nothing reads as
evidence. A PR that could shift ranking (`search/params.py`, the chunk budget, a scoring
lane, the embedding wire) is gated on it — say so in the description so it gets run, and
expect the three numbers (`R@1`, `bundle_full`, `p50`) in the commit message.

## Adding a language (the best first contribution)

A language is a config entry, not a subsystem:

1. Add a spec in `chunkers/treesitter/specs/` (node types → kinds, name/body fields,
   export unwrap). `optional.py` has the tricky cases — Rust's `impl` blocks, PHP's
   namespaced names.
2. Add a module in `chunkers/languages/` — they are 13–18 lines each; copy `go.py`.
3. Register the extensions and the `tree_sitter_<lang>` module in
   `indexing/_languages.py`, so it activates **only** when that grammar imports and a
   missing wheel costs that language and nothing else.
4. Add the grammar to the `languages` extra in `pyproject.toml`.
5. Add a test that feeds real-world-shaped source and asserts
   `validate_partition(result) == []` plus sensible symbols and kinds. Copy the structure
   of the existing chunker tests, and use source that looks like a real file — the two
   declaration shapes this engine had to learn (a CommonJS `res.send = function () {}`
   and a mocha `it('…', fn)`) were both invisible to tidy fixtures.

Level 2, optional: an import/call edge extractor in `indexing/edges/`. Retrieval works
without one — edges only add graph candidates and map annotations — and bumping
`EDGE_SCHEMA` is what makes existing indexes rebuild their graph with no re-embedding.

A private format or DSL does not need a PR at all: implement the `Strategy` **Protocol**
(an object with `exts`, `parse`, `edge_context`, `edges` — no import, no inheritance) and
pass it to `index_repo(root, strategies=[...])`. Injected strategies are consulted before
the built-ins, so you can override a shipped extension too.

## Style

`./scripts/lint` must pass (all config in `pyproject.toml`, every exclusion justified in
a comment there). Match the codebase's voice: comments explain **why** — the constraint,
the measurement, the failure that produced the line — never what the code plainly says.
A constant with no evidence beside it is the thing this codebase does not have.

## Releasing (maintainers)

**Versioning policy: patch-first, release-when-it-matters.** Merging to `master` does not
imply a release; a version is published when there is a concrete reason. A breaking
change to a public contract (CLI, MCP, HTTP, the Python API) takes the minor.

Mechanics: bump `src/megabrain/_version.py:__version__` (the one place — `pyproject.toml`
reads it from there), add a `## X.Y.Z — title` section to `CHANGELOG.md` (that section
*becomes* the GitHub release notes, never written twice), then
`git tag vX.Y.Z && git push origin vX.Y.Z`.

`release.yml` takes over and **cannot publish something broken**: `publish` needs `guard`
(the tag must equal `__version__`) plus `gates` (this repo's `ci.yml`, invoked through
`workflow_call`, so lint and the whole OS × Python matrix run against the tagged commit).
Publishing is tag-only and goes to PyPI via Trusted Publishing — OIDC, no token. To
rehearse without burning a version: `gh workflow run release.yml --ref master`, where
everything runs and `publish` skips.
