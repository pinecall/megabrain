<p align="center">
  <img src="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/megabrain.png" alt="megabrain" width="180">
</p>

<h1 align="center">megabrain</h1>

<p align="center">
  <b>Ask a codebase a question. Get the exact code back.</b>
</p>

<p align="center">
  <sub>The repo walk your coding agent does in <b>10–30 grep-and-open turns</b> — in <b>one call</b>.</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/megabrain/"><img src="https://img.shields.io/pypi/v/megabrain?style=flat-square&color=3776AB" alt="PyPI"></a>
  <a href="https://github.com/bernatch22/megabrain/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/bernatch22/megabrain/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT">
  <img src="https://img.shields.io/badge/retrieval-no%20LLM%20·%20milliseconds-2ea44f?style=flat-square" alt="No LLM in the retrieval path">
  <img src="https://img.shields.io/badge/MCP-4%20tools-000000?style=flat-square" alt="MCP ready">
</p>

<br>

Point megabrain at a repo and ask **"how does auth work"** in plain English. It finds all
the related code in **milliseconds** with **no LLM** — just math on embeddings, in **one
SQLite file**. No vector DB, no containers, no services.

Want it *explained*? `ask` adds one LLM call that narrates a walkthrough with the **real
code spliced in from disk**, line for line. The model only ever *points* at code — it
cannot rewrite a line, so nothing is invented.

<br>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-light.png">
    <img alt="megabrain studio's Ask tab on sinatra: one question served instantly from the flow cache, and below it a live synthesis — retrieval in 25 ms across 14 files, then the cited answer streaming with the real code spliced in." src="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-light.png" width="900">
  </picture>
</p>

<p align="center">
  <sub><code>megabrain studio</code> — the whole engine in your browser</sub>
  <br><br>
  <a href="https://bernardocastro.dev/megabrain/demo/"><b>Try it live →</b></a>
</p>

<br>

---

## Quickstart

**Note the argument order: the question comes first, the path second — and the path
defaults to `.`, so inside the repo you can leave it off.**

### One key, nothing to configure

```bash
pip install megabrain
export OPENROUTER_API_KEY=sk-or-...

megabrain index ~/repo                                  # once — incremental after
megabrain ask   "how does auth work end to end" ~/repo
```

That single key gets you the whole validated stack, and it is already the default:

- **`perplexity/pplx-embed-v1-0.6b`** for retrieval — the measured best for code recall.
  It beat pplx-4b, codestral-embed, openai-3-large and bge-m3 in a head-to-head bakeoff
  (R@1 **0.864**, bundle_full **0.955**).
- **`google/gemini-3.1-flash-lite`** narrates, **`google/gemini-3.5-flash-lite`** judges.
  Two constants because the jobs are not the same: narration reasons about a flow in
  prose, the judge emits a short id array. Measured over 20 mined cases × 3 repetitions,
  3.5-lite prunes one file tighter every time — and *bigger is worse*, also measured:
  reasoning models return empty (thinking eats the token cap) and plain
  `gemini-3.5-flash`, five times the price, failed open at 5.6 s.

Every default here is a measurement, not a guess. → [the numbers](docs/GUIDE.md#providers-and-models)

### Narrating through the Claude Agent SDK

An alternative to the chat endpoint: drive the bundled Claude Code binary instead of
OpenRouter. Retrieval is untouched — it never calls a model — and embeddings keep their own
key, because Anthropic has no embeddings API.

```bash
pip install 'megabrain[claude]'
export MEGABRAIN_CHAT_PROVIDER=claude     # opt-in; never selected on its own
export MEGABRAIN_ASK_MODEL=haiku          # optional — CLI names, not `vendor/model`
unset ANTHROPIC_API_KEY                   # ← see below. Not optional.
```

**`ANTHROPIC_API_KEY` takes precedence over the Claude Code login, and it wins silently.**
With one exported, the run bills that API account and never touches the local login —
which, if the key belongs to an account with no credit, ends the call with
`the Claude CLI refused the run: Credit balance is too low` while a perfectly good login
sits unused. The CLI prints a warning about this and it is easy to read past. Unset the
variable to use the local login; export it to bill that API account deliberately. Bedrock
and Vertex are selected with the variables the SDK documents.

**This lane narrates from the retrieved material without opening extra files** — the SDK
runs its own tool loop, so `ask` answers in one pass instead of reading its way down a call
chain. Measured on this repository, `haiku`, 24 candidates: **27 s end to end, first token
at 14 s, 48 streamed deltas**. The HTTP lane stays the default for a reason.

### Fully local — Ollama for both halves, zero cloud

Air-gapped, $0, open weights end to end, and **your code never leaves the machine**:

```bash
pip install 'megabrain[languages]'
ollama pull bge-m3 && ollama pull qwen3-coder:30b

export MEGABRAIN_EMBED_BASE_URL=http://localhost:11434/v1
export MEGABRAIN_EMBED_MODEL=bge-m3
export MEGABRAIN_CHAT_BASE_URL=http://localhost:11434/v1
export MEGABRAIN_ASK_MODEL=qwen3-coder:30b

export MEGABRAIN_ASK_CTX_CHARS=105000     # ← required: see below
export OLLAMA_CONTEXT_LENGTH=40960

megabrain index ~/repo --force            # --force re-embeds with the new model
megabrain ask   "how does auth work end to end" ~/repo
```

A local endpoint needs **no key** — megabrain recognises a loopback URL and skips the
credential check entirely.

**Use a real coder model.** `qwen3-coder` is the one that holds up — the small dense
models are not a cheaper trade-off, they cite less *and* run slower, and a
general-purpose model of the same size does markedly worse on code.

**`MEGABRAIN_ASK_CTX_CHARS` is not optional.** The prompt budget defaults to 200 000
characters, sized for cloud context windows, so a local model silently gets a truncated
prompt — no error, just quietly worse answers. Compared to the cloud you lose some
*secondary* citations, never correctness: the code you are shown is still spliced
verbatim from disk.

`bge-m3` is the local embedder to use. It matches the cloud one on the measure that
decides whether `ask` gets the right code at all, and trails it on ranking the single
best file first — a real trade, and a small one.

**[The numbers, and the extra knob thinking models need →](docs/RECIPES.md#run-fully-local--no-keys-no-cloud)**

---

Python, JS/TS and Markdown work out of the box. `pip install 'megabrain[languages]'`
adds Ruby · Go · Rust · PHP · C · C++ · Java · C# — eight wheels with native code in
them, which is why a default install does not carry them.
Every setup, with its cost: **[Guide](docs/GUIDE.md#1-install-and-your-first-answer)**.

---

## What you get

**Retrieval that cannot hallucinate.** The search path has no LLM at all — dense chunk
vectors fused with a file-skeleton signal and the import/call graph. It is enforced by a
test that walks imports, not by discipline. The narrator only ever *cites* spans and the
engine splices the verbatim bytes, so no line is ever invented. Two optional model lanes
ride on top — [`--rerank` for order, `--expand` for recall](docs/GUIDE.md#2-the-two-ways-to-ask)
— both off by default, both fail-open, neither inside the core path.

**`ask` — the repo, explained.** One call returns a senior-engineer walkthrough of the
whole cross-file flow, with the real code spliced in at each step. The narrator **opens
whatever the retrieved chunks left unexplained** — the definition a call lands on, the
test that pins the behaviour — and keeps reading until the answer is complete. Broad
questions [fan out into parallel sub-agents](docs/GUIDE.md#2-the-two-ways-to-ask), one per
subsystem, and a synthesizer merges their cited answers.

**It learns from itself.** Every `ask` caches its walkthrough. Ask again — even reworded —
and it serves in **~0 ms with zero LLM** (measured 27.8 s → 0.19 s), guarded by a
byte-level sha recheck so it can never describe code that changed.
[How it works →](docs/GUIDE.md#5-it-remembers--the-flow-cache)

**A knowledge graph, for free.** The same index doubles as a navigable map: clusters, the
core "god node" files, and the real call-path between any two files — built from AST edges
plus embedding similarity, numpy only, no networkx.
[What it's actually good for →](docs/GUIDE.md#4-map-the-repo-with-the-graph)

**The answer is a MAP, not a wall of code.** `search` returns the files that answer the
task, each with its best-matching span (true line numbers) and the symbols it declares —
**~2 700 tokens against ~8 100 with bodies**, measured on a real bundle. The span already
says which lines to open, so the code is one `--full` away when you want it and never in
the way when you do not.

**A local studio.** `megabrain studio` opens the whole engine in your browser: search,
ask, the flow cache and the graph on a live canvas, plus a read-only code navigator
where every identifier is a go-to-definition link.
[Take the tour →](docs/GUIDE.md#3-the-studio)

**Everywhere you work.** A terminal CLI, an MCP server inside Claude Code / Codex /
Cursor / Windsurf / Gemini CLI / Antigravity, a Python library, and the studio.

---

## For coding agents

This is what megabrain is *for*. Dropped into an unfamiliar repo, an agent burns 10–30
tool turns — grep, open a file, follow an import, grep again — before it writes a line,
and the picture it assembles is still its own guess.

```bash
megabrain install    # detects Claude Code · Codex · Cursor · Windsurf · Gemini CLI · Antigravity
```

|  | by hand | one megabrain call |
|---|---|---|
| tool turns | 10–30 | **1** |
| what lands in context | whole files, mostly irrelevant | **exactly the signal chunks** |
| the cross-file story | reconstructed, unverified | **narrated, real code spliced in** |
| asking it again later | the full re-exploration | **~0 ms, from the cache** |

### Four tools, one retrieval core

Three of them run the same deterministic retrieval and differ only in **what they hand
back** — because "find me this code" is three different jobs, and answering all three the
same way is what makes a tool feel almost useful. The fourth makes a repo answerable.

| you are about to… | tool | what comes back | size |
|---|---|---|---|
| **EDIT** — you know roughly what to change | **`megabrain_grep`** | the files to open, the symbols in them worth opening, each one's **exact line range**. **The lanes run no model**: identifiers from your task matched against the index, plus one hop to the contracts those sites reference | a few hundred to ~2k chars, **~50 ms of lanes** |
| **UNDERSTAND** — a mechanism, a bug, or a pattern you want to copy out of another repo | **`megabrain_ask`** | the flow narrated end to end with the **real code spliced in**, plus the definition of every helper it names and the tests that pin what it described | ~1–2k words |
| read the **DOCS**, or get the map | **`megabrain_search`** | the files that answer, each with its best span and symbols. `content: "docs"` for prose — this is the one to reach for when a repo's README *is* the API reference | ~2 700 tokens |
| make a repo answerable | **`megabrain_index`** | the index, incremental by content hash | — |

Each `inputSchema` is generated from `contracts/tools.py`, so a parameter cannot exist on
the wire without existing in the dispatch.

### Why `grep` quotes no code, on purpose

Your editor makes you open the file to change it. So a tool that pastes the body has
billed you for reading it twice — and that is not a guess, it is why the earlier
`megabrain_code` was **deleted**: measured across five tasks in three languages, the
retrieval was excellent and the citation was waste.

What no editor and no `grep` can give you is the **line range of the thing that matters**:

```
$ megabrain grep "the read tool refuses non-regular files but write does not — add the guard" \
    ~/experiments/anthropic-sdk-python

## src/anthropic/lib/tools/agent_toolset.py
  in scope: annotations, os, re, uuid, base64, shutil, logging, subprocess, S_ISREG, …
  L567-616  beta_read_tool — the guard to copy for non-regular file rejection
  L619-634  beta_write_tool — add the non-regular file guard here to match read tool

## tests/lib/tools/test_agent_toolset.py
  in scope: annotations, os, sys, base64, Any, cast, Path, Required, get_args, …
  L340-345  test_edit_binary_raises_tool_error — add a test case here for writing to a non-regular file
```

That is the real output, trimmed to the first two of five files (the whole answer is
1 690 characters, 8 rows). `grep -r "regular file"` finds the string; this finds the
**place with no matching string at all** — `beta_write_tool`, which is the whole point,
because the code you have to change is the code that does not yet mention the thing. The
`in scope:` line is what the file already has imported, so you know whether the guard's
helper (`S_ISREG`, here) needs an import added.

**And the lanes run no model to do it.** That was measured after being built the wrong
way round: on click's `show_envvar_value` task the deterministic lanes alone returned 10 of 11
rows in **0.05 s**, while adding a model pass took **1.3 s** — 26× — for one extra row and
a note on each. A tool that stands in for `grep` cannot charge a model call by default.
`--why` / `why: true` buys that row back: it is the one no literal search can reach, whose
text never contains the task's own words.

Two honest caveats about that number. The ~50 ms is the **lanes**; the wall clock also
carries one round trip to embed your task (content-addressed, so a repeated one is free)
and Python's startup. And a task that names **no identifier the index knows** would return
zero rows — measured across ten repositories, eight of ten tasks phrased as pure outcome
did exactly that — so that case alone falls back to the model pass rather than answering
empty. Fast and wrong is worse than a second and right.

The split of labour inside is deliberate: the model names the symbol, the **engine** reads
the line range out of the symbol table. Asking a model for line numbers was measured and
rejected — unnumbered, its ranges "landed a few lines off and cut functions mid-body".

**The test suite counts as a place to look, and in JS it used to be invisible.** A mocha or
jest file declares its units by *calling* a function with a label and a closure, which the
grammar reads as an expression statement — so express's `test/res.attachment.js` was
indexed with two symbols, both `require` bindings, and since a match resolves to the
symbol *containing* it, no row could land inside any test file in a JS repository. Those
blocks are symbols now (express: **3.9 → 12.3 symbols per file**), and every row respects
one quota: **all of the implementation, a sample of the tests** — `sendFile` has three
implementation sites and 44 cases, and the reader needs one example, not forty-four.

If you indexed a repo before this, a plain `megabrain index` picks it up with **zero
embedding calls** — symbols cost a parse, so re-extracting them is free.

**Measured against the `grep` it replaces**, on click, express and sinatra at pinned
commits: the same job costs **4 074 tokens against 20 715** (5.1×) — or against 110 499
(27×) when the hit lands in a 3 600-line module and you read the file. Coverage **7 of 7
sites against 6 of 7**, and the one grep cannot reach is the one that breaks the change: a
`TypedDict` whose text never contains the string you searched for. Latency is a tie
(milliseconds either way — the saving is tokens and turns, and anyone selling you speed
here is selling you nothing).

**[The tables, the method, and where it is biased →](docs/BENCHMARKS.md)** — reproduce with
`./benchmarks/setup.sh && python benchmarks/measure.py`.

### Why `search` is never the input for an edit

`search` hands you chunks straight from the index with no model in the loop, which makes it
the fastest and the most honest of the three — and unusable for a change. It **ranks what
exists**, so when the bug is a missing call, an unset flag or an absent guard, the very
thing you need is the one thing it cannot rank. Reach for it to read a repo's docs
(`content: "docs"`) or to get your bearings; reach for `grep` to edit.

> **Put this in your agent's rules:** about to change code in an indexed repo →
> `megabrain_grep`, not `grep`. Want to understand a mechanism or copy a pattern from
> another project → `megabrain_ask`. Reading documentation → `megabrain_search` with
> `content: "docs"`. Never chain one call per sub-question: one call covers a task.

[Every parameter →](docs/REFERENCE.md#mcp-tools) ·
[Wiring recipes →](docs/RECIPES.md#give-your-coding-agent-the-whole-repo)

---

## Commands

Nine verbs. The query comes first and the path is optional — `[path]` may be **any
sub-path inside an indexed repo**, and retrieval is scoped to files under it.

```bash
megabrain index  [path]                        # build / update the index (incremental)
megabrain scan   [path]                        # census only: what WOULD index, and skips
megabrain search "retry logic" [path]          # the code map, no LLM
megabrain search "retry logic" --full          #   …with the code bodies inline
megabrain ask    "how does X work" [path]      # narrated walkthrough + real code
megabrain grep   "add a retry to X" [path]     # where to edit: files, symbols, line ranges
megabrain get    path/to/file.py [path]        # one file, or one symbol
megabrain graph  [path]                        # the repo as a knowledge graph
megabrain studio                               # the web UI + JSON API on :2137
megabrain install                              # register the MCP server with your assistants
```

[Every command and flag →](docs/REFERENCE.md#cli)

### `megabrain.json` — what a repository decides about itself

Optional, committed, and visible on purpose: the dot marks what you ignore, and this is
the file meant to be found and edited by whoever clones the repo.

```json
{
  "ignore":  ["dist", "vendor/**"],
  "gitignore": true,
  "queries": ["how does the retry policy work?"],
  "models":  {"narrator": "google/gemini-3.1-flash-lite",
              "rerank":   "google/gemini-3.5-flash-lite"}
}
```

An explicit argument beats the file, the file beats the environment, the environment beats
the built-in default. A config that TRAVELS is the point: an env var lives in one shell
and is invisible to everyone else, which is how a repo ends up indexed differently by two
people on the same team. Nothing here is required, and a malformed field is ignored on its
own without taking the rest of the file down. [Every field →](docs/REFERENCE.md#config-files)

---

## Measured, not vibes

Against [claude-context](https://github.com/zilliztech/claude-context) (Zilliz), the
closest open-source peer — same repo, same 22 hand-labelled questions, both at their best:

|  | megabrain | claude-context |
|---|---|---|
| **R@1** | **0.864** | 0.818 |
| **R@5** | **1.000** | 0.909 |
| search latency | **~22 ms** warm | ~1400 ms |
| vector store | **one SQLite file** | Milvus + etcd + MinIO |
| narrated answer | **yes** — real code spliced in | no (returns chunks) |

The golden set is ours, on a corpus megabrain was tuned against — treat the absolute
numbers as home-field and run it yourself.
[Full method, caveats and the embedding bakeoff →](ARCHITECTURE.md#8-evidence-where-the-numbers-live)

---

## Docs

- **[Guide](docs/GUIDE.md)** — the tour, front to back: setup → search vs ask → the studio
  → the graph → the flow cache → MCP → new file types → tuning
- **[Recipes](docs/RECIPES.md)** — "I want to ___": private repos, team knowledge bases,
  public demos, custom file types, cost and speed
- **[Reference](docs/REFERENCE.md)** — every CLI flag, MCP tool, HTTP route and env var
- **[Benchmarks](docs/BENCHMARKS.md)** — the token measurements, reproducible
- **[Architecture](ARCHITECTURE.md)** — how it's built and **why**: the locked design
  rules and the experiments behind them
- **[Contributing](CONTRIBUTING.md)** — the best first PR is a new language
- **[Changelog](CHANGELOG.md)** — what changed, and why

<br>

---

<p align="center"><sub>MIT · github.com/bernatch22/megabrain</sub></p>
