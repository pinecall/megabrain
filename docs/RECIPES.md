# Recipes

Concrete goals, copy-paste answers. New here? Read the **[Guide](GUIDE.md)** first —
it's the tour. Looking up a flag? → **[Reference](REFERENCE.md)**.

- [Give your coding agent the whole repo](#give-your-coding-agent-the-whole-repo)
- [Run fully local — no keys, no cloud](#run-fully-local--no-keys-no-cloud)
- [Turn a repo into a team knowledge base](#turn-a-repo-into-a-team-knowledge-base)
- [Run a public read-only demo](#run-a-public-read-only-demo)
- [Make it read a file type it doesn't know](#make-it-read-a-file-type-it-doesnt-know)
- [Use it as a Python library](#use-it-as-a-python-library)
- [Make ask cheaper, or faster](#make-ask-cheaper-or-faster)
- [Keep secrets and junk out of the index](#keep-secrets-and-junk-out-of-the-index)

---

## Give your coding agent the whole repo

```bash
megabrain install                 # registers the MCP server everywhere it's detected
megabrain index ~/repo            # once per repo you want the agent to see
```

Then put **this** in your agent's rules file (`CLAUDE.md`, `.cursorrules`, a skill —
whatever your assistant reads):

> **About to change code in an indexed repo → `megabrain_grep`, not `grep`.** For any
> question about how the code works — a flow, where something is handled, why a value is
> what it is — call **`megabrain_ask` FIRST**, before grepping or reading files. Reading
> documentation → `megabrain_search` with `content: "docs"`. Never chain one call per
> sub-question: one call covers a task.

That one instruction is the difference between an agent that burns 15 turns reconstructing
a flow and one that gets it in a single grounded call.

**Which tool for which agent?** All of them are grounded — pick by who does the reasoning:

- **`megabrain_grep`** — for the *edit*. The lanes run no model, ~50 ms: the files to
  open, the symbols worth opening, each one's exact line range. It finds the site whose
  text never contains your search terms, which is the one a `grep` cannot reach. **Name
  the identifiers you already know** — a task phrased as pure outcome names nothing the
  index has, and then it falls back to one model pass rather than returning nothing.
- **`megabrain_search`** — for a strong agent that wants to reason over raw code itself.
  Milliseconds of no-LLM retrieval returns the exact spans worth reading;
  `bodies: true` inlines the code, `rerank: true` adds a judge call that reorders what
  vocabulary alone put in the wrong order (off by default — the deterministic answer is
  complete on its own).
- **`megabrain_ask`** — the repo *explained*. This is relevance curation for whatever model
  reads it: an agent on a smaller, cheaper LLM that could never navigate the repo alone
  gets handed the connected story, already assembled and grounded.

**What you give up versus the cloud** is *secondary*-citation completeness, not
correctness. The citation/splice mechanism is model-agnostic — every model tested spliced
real code on most queries — so a weaker narrator cites fewer surrounding files but never
invents one, and the primary answer file is essentially always in the bundle either way.

---

## Run fully local — no keys, no cloud

Air-gapped, $0, open weights end to end. Both halves are independent, so you can also do
half of this (local embeddings + cloud narrator, or the reverse).

```bash
pip install 'megabrain[languages]'
ollama pull bge-m3 && ollama pull qwen3-coder:30b

export MEGABRAIN_EMBED_BASE_URL=http://localhost:11434/v1
export MEGABRAIN_EMBED_MODEL=bge-m3
export MEGABRAIN_CHAT_BASE_URL=http://localhost:11434/v1
export MEGABRAIN_ASK_MODEL=qwen3-coder:30b

export MEGABRAIN_ASK_CTX_CHARS=105000      # ← required, see below
export OLLAMA_CONTEXT_LENGTH=40960         # Ollama's own default (2048) truncates the prompt

megabrain index ~/repo --force             # --force re-embeds with the new model
megabrain ask   "how does auth work" ~/repo
```

**No key is needed.** A loopback base URL is recognised as local and the credential check
is skipped entirely — an earlier version demanded a key for `localhost` and refused to run.

**`MEGABRAIN_ASK_CTX_CHARS` is not optional.** The prompt budget defaults to **200 000**
characters, sized for cloud context windows. A local model silently gets a truncated
prompt — no error, just quietly worse answers.

**Use a real coder model.** `qwen3-coder` is the one that holds up:

- **The lightweight dense models lose on both axes.** They cite fewer files *and* run ~2.7×
  slower (~41 s vs 15 s) — they think harder per token with no MoE speedup. Being frugal
  buys you a worse *and* slower narrator, not a trade.
- **Code specialization is not cosmetic.** The general-purpose sibling of the very same 30B
  MoE scores **half** the citation recall on a code corpus (0.333 vs 0.583).
- **A thinking model needs one more knob.** If the model emits reasoning tokens, they eat
  the output budget before the walkthrough starts. Prefer a non-thinking coder model here.

**`bge-m3` is the local embedder to use.** It ties the cloud default on completeness
(bundle_full) and ranks the single best file first less often (R@1 0.773 vs 0.864) — a real
trade, and a small one.

---

## Turn a repo into a team knowledge base

The [flow cache](GUIDE.md#5-it-remembers--the-flow-cache) makes megabrain accumulate your
team's understanding: every `ask` is stored, and a repeat — even reworded — is served with
no model call. Two things make that deliberate instead of incidental.

**1. Commit the questions.** `megabrain.json` at the repo root:

```json
{
  "queries": [
    "How does a request get authenticated end to end?",
    "How does the billing webhook reconcile a payment?",
    "How does the job queue retry a failed task?"
  ]
}
```

That single field does two jobs: it documents the repo's main flows for a newcomer, **and**
it becomes the [starter chips](GUIDE.md#starter-questions) in the studio (a repo that
declares none gets chips *derived* from its most depended-on files instead). Click through
them once and every chip then serves instantly with no LLM. *(The legacy
`.megabrainqueries`, one question per line with `#` comments, is still read and merged.)*

**2. Decide who owns the cache.** Everything lives in the repo's own
`.megabrain/db.sqlite`. Commit it and the whole team inherits the answers; leave it
gitignored and each machine builds its own.

A cached answer can never outlive its code: every flow records the sha256 of each file it
cites and re-checks them byte-for-byte before serving.

---

## Run a public read-only demo

Serve the real studio publicly without letting visitors index anything or burn your budget.

```bash
megabrain ui --readonly --rate-limit 30 --port 2137
```

- `--readonly` — 403s every mutating route (index, scan). Enforced **server-side**; the UI
  also hides those affordances because it reads `GET /config`, but the lock never depends on
  the UI.
- `--rate-limit 30` — at most 30 requests per minute per caller.
- `--token "$(openssl rand -hex 16)"` — requires a Bearer header on every route except
  `/health`, `/config` and the UI itself. Also read from `$MEGABRAIN_API_TOKEN`.

nginx, mounted under a path prefix:

```nginx
location /megabrain/demo/ask/stream {     # SSE needs buffering off + a long timeout
    proxy_pass http://127.0.0.1:2137/ask/stream;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
location /megabrain/demo/ {
    proxy_pass http://127.0.0.1:2137/;
}
```

This is how [bernardocastro.dev/megabrain/demo](https://bernardocastro.dev/megabrain/demo/)
runs. Bind to loopback and let the proxy be the only thing facing the internet — that is
already the default host.

---

## Make it read a file type it doesn't know

`.toml`, `.astro`, `.proto`, a private DSL — anything outside the built-in languages is
invisible to retrieval. The extension point is a Protocol: write an object with `exts`,
`parse`, `edge_context` and `edges`, and pass it to `index_repo`.

```python
index_repo("~/repo", strategies=[TomlStrategy()])
```

Injected strategies are consulted **before** the built-ins, so this also overrides a
shipped extension rather than only claiming an unhandled one. The one hard gate is checked,
not trusted: your chunks must form an **exact line partition** of every file you claim, and
the index report counts any violation.

Full shape and the reason it is a Protocol: [Guide §7](GUIDE.md#7-teach-it-your-file-types).

---

## Use it as a Python library

Everything the engine does is importable, lazily and with types — `import megabrain` costs
no numpy and no tree_sitter, because every public name resolves on first access.

```python
from megabrain import index_repo, search, load_state, search_with_state
from megabrain.usecases import ask, grep, get_code

index_repo("~/repo")                                    # incremental

bundle = search("~/repo", "retry logic")                # no LLM anywhere -> Bundle
print(bundle["tier1"][0]["file"])

state = load_state("~/repo")                            # warm: load the matrices once
with state:                                             # …then query many times
    for _ in range(100):
        bundle = search_with_state(state, "retry logic")

print(ask("~/repo", "how does auth work"))              # narrated + spliced
print(grep("~/repo", "add a retry to the embed call"))  # files, symbols, line ranges
```

Public API: `index_repo · discover · search · search_with_state · load_state ·
score_chunks · Store · ChunkMeta · Strategy · Registry · Chunk · Symbol · FileResult ·
validate_partition` + the error taxonomy (`MegabrainError`, `IndexNotFound`, `EmptyIndex`,
`MissingCredential`, `MissingAPIKey`, `ProviderError`, `ModelMismatch`). The verbs the CLI
and MCP call live in `megabrain.usecases` — one file per verb, sync, returning the same
`contracts/` payloads the wire serves.

Errors carry a machine `code` and keep their old base classes, so `except ValueError` from
before still works: `IndexNotFound(MegabrainError, ValueError)`.

---

## Make ask cheaper, or faster

`ask` is **output-bound** — the narration dominates, not retrieval. So the model choice is
the whole lever:

```bash
export MEGABRAIN_ASK_MODEL=qwen/qwen3-coder                 # cheapest: ~$0.0035/ask, ~14 s
export MEGABRAIN_ASK_MODEL=google/gemini-3.1-flash-lite     # the default: fastest
```

Or commit it, so it applies to everyone on the repo:

```json
{ "models": { "narrator": "qwen/qwen3-coder" } }
```

Three ways to pay less that aren't model swaps:

1. **Let the cache work.** A repeated question costs **$0 and ~0 ms**. Ask the repo's main
   workflows once and most questions never reach a model again.
2. **Use `search` when you don't need prose.** Zero LLM, milliseconds, and a capable agent
   reads raw code fine. `--full` when you want the bodies.
3. **Keep the fan-out small.** `MEGABRAIN_MAX_AGENTS` (default 4) caps how many sub-agents
   a broad question may spawn; `MEGABRAIN_AGENT_TIMEOUT` (default 300 s) bounds each one.

The judge has its own knob (`MEGABRAIN_RERANK_MODEL`, or `models.rerank`), and it should
stay a cheap fast model — measured, a bigger one is *worse* as well as slower, because the
job is emitting a short id array, not reasoning. Reranking is off by default, so a repo
that configures nothing pays nothing.

---

## Keep secrets and junk out of the index

```bash
megabrain scan ~/repo                    # census: what WOULD index, and everything skipped + why
megabrain index ~/repo --exclude 'vendor/**' --exclude '*.min.js'
```

Better than a flag you have to remember — commit it:

```json
{ "ignore": ["dist", "vendor/**", "tests/fixtures"], "gitignore": true }
```

`gitignore` defaults to **true**: whatever the repo already declared as build output is not
source. That is right for `bin/`, `dist/`, dead snapshots — and it has a real false
positive, found in megabrain's own history: an `evals/` directory that was gitignored *and*
was source. The escape is this committed field rather than a flag, because whoever hits it
knows their repo and the next person to clone should inherit the answer.

`scan` names each skip with its reason — `excluded` · `gitignored` · `too-big` (over 600 KB,
where a megabyte of generated data embeds into one meaningless direction and buries the file
that answers the question) · `unreadable` — so you see what the filters would drop before
committing to them. It names the files too, because "3 unreadable" tells nobody which three.

Build, vendor and cache directories are excluded everywhere with no configuration
(`node_modules`, `dist`, `build`, `target`, `vendor`, `Pods`, `.venv`, `__pycache__`, …), and
so are `CLAUDE.md` / `AGENTS.md`: those are instructions for whoever reads the repo, not
content of it, and indexing them feeds a search its own operating rules back as
documentation.
*(The legacy `.megabrainignore`, one pattern per line and no `!` negation, is still read
and merged.)*

Deleting an index is `rm -rf ~/repo/.megabrain`. There's no command for it, on purpose.
