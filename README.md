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
  <a href="https://pypi.org/project/megabrain/"><img src="https://img.shields.io/badge/version-1.0.0-3776AB?style=flat-square" alt="v1.0.0"></a>
  <a href="https://github.com/bernatch22/megabrain/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/bernatch22/megabrain/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT">
  <img src="https://img.shields.io/badge/retrieval-no%20LLM%20·%20milliseconds-2ea44f?style=flat-square" alt="No LLM in the retrieval path">
  <img src="https://img.shields.io/badge/MCP-4%20tools-000000?style=flat-square" alt="MCP ready">
</p>

<br>

```
$ megabrain ask "how does auth work end to end" ~/repo
· retrieved in 12ms — 3 core, 14 related          ← deterministic, no LLM, already the answer
· narrating over 24 chunks…                       ← one model call, code spliced VERBATIM from disk
```

No vector DB. No containers. No services. **One SQLite file** per repo, math on
embeddings, and a hard rule with a test behind it: **the model can point at code,
it can never write it.**

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-light.png">
    <img alt="megabrain studio: retrieval lands in 25 ms across 14 files, then the cited answer streams with the real code spliced in." src="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-light.png" width="900">
  </picture>
</p>

<p align="center">
  <sub><code>megabrain studio</code> — the whole engine in your browser</sub>
  <br><br>
  <a href="https://bernardocastro.dev/megabrain/demo/"><b>Try it live →</b></a>
</p>

---

## 60 seconds

```bash
pip install megabrain
export OPENROUTER_API_KEY=sk-or-...

megabrain index ~/repo                       # once — incremental by content hash after
megabrain ask  "how does auth work" ~/repo   # question FIRST, path second (defaults to .)
megabrain install                            # wire the MCP server into Claude Code, Codex,
                                             # Cursor, Windsurf, Gemini CLI, Antigravity
```

One key gets the whole measured stack: `pplx-embed-v1-0.6b` for retrieval (won the
bakeoff against pplx-4b, codestral-embed, openai-3-large, bge-m3),
`gemini-3.1-flash-lite` narrates, `gemini-3.5-flash-lite` judges. Every default is
a measurement, not a guess → [the numbers](docs/GUIDE.md#providers-and-models).

---

## Three verbs, three jobs

"Find me this code" is **three different jobs**, and answering all three the same
way is what makes most code-search tools feel almost useful. megabrain ships one
deterministic retrieval core and three deliverables on top of it:

| you are about to… | verb | what comes back | LLM? |
|---|---|---|---|
| **EDIT** code | `grep` | files + symbols + **exact line ranges**, zero code quoted | **no** (~50 ms) |
| **UNDERSTAND** a flow, or copy a pattern from another repo | `ask` | the walkthrough, real code **spliced verbatim** from the index | 1 call |
| read the **DOCS**, or get the map | `search` | ranked files, best span each, symbols — instant | **no** |

### `grep` — when you are going to edit. Use this one to go FAST.

You hand it the **task**, it hands you every file the change has to touch — with
the exact range to jump to:

```
$ megabrain grep "Option has show_envvar; add show_envvar_value" ~/click

## src/click/core.py
  in scope: os, typing, ParamType, …
  L2944-3023  Option.__init__ — declare the new keyword argument
  L3106-3130  Option.get_help_extra — where the flag must be read, or it does nothing
## src/click/types.py
  L1045-1050  OptionHelpExtra — the TypedDict that gains a key
## tests/test_options.py
  L758-766    test_show_envvar — the test to imitate
```

Three things `grep -rn` structurally cannot do:

1. **It resolves a match to the symbol containing it.** "Line 2952" becomes
   "`Option.__init__`, L2944-3023" — a place to *jump*, not a place to start reading.
2. **It reaches the site with no matching string.** `OptionHelpExtra`'s text never
   contains `show_envvar` — it is found by following the return type the sites
   already declare. Miss it and you ship a flag that parses, stores, and never
   shows up. **Coverage: 7/7 sites vs grep's 6/7**, and the missed one is always
   this kind.
3. **It quotes no code, on purpose.** Your editor opens the file to edit it — a
   tool that pastes the body bills you for reading it twice. Measured on the whole
   job (find + read): **4,074 tokens vs 20,715** for grep+windows (5.1×), vs
   **110,499** (27×) when the hit lands in a 3,600-line module.

The lanes run **no model** (that is the whole reason it can stand in for `grep`);
`--why` adds one call for a note per row. Name the identifiers you already know —
"Option has show_envvar; add X" beats "make the help show env values", measured 4×.

### `ask` — when you need to understand. NOT when you're about to edit your own code.

The flow narrated end to end, the real bytes spliced at every citation, plus —
deterministically, no extra model call — the definition of every helper the prose
names and **the tests that pin the behaviour** (the one 1,600 lines away that your
change breaks and nobody cited). The narrator *opens files* the retrieved chunks
left unexplained and keeps reading until the answer is complete: **19 tool calls
by hand vs 6**, on a 1,220-file repo.

Where it shines: **understanding a mechanism in a big repo you don't know, or
copying a pattern out of another project.** `megabrain ask ~/other-repo "how does
their retry loop classify errors"` is the fastest way to steal a design correctly.

Where it's the wrong tool: **right before an edit in your own repo.** Your agent
will `Read` the files before touching them anyway — it must — so an `ask` answer
puts the same code in context **twice**, and a context with two copies of the
truth is how an LLM gets confused about which one it's editing. About to edit →
`grep`. Need the story → `ask`.

The prose is narration; the **code is verbatim**. Check the first against the second.

### `search` — instant, zero LLM, and the docs reader

Embeddings straight from the index: the files that answer, each with its best
span (true line numbers) and its symbols. **~2,700 tokens vs ~8,100 with bodies**;
the span already says which lines to open. `--full` inlines the code,
`content: "docs"` searches the indexed markdown — when a repo's README *is* the
API reference, this is the verb.

Two opt-in model lanes ride on top, both fail-open, neither in the core path:
`--rerank` (order — a judge drops vocabulary-only look-alikes, never a file) and
`--expand` (recall — a model names the identifiers your wording missed, the
**symbol table** resolves them; a name it can't resolve is dropped, not guessed).

One honest limit: `search` **ranks what exists**. When the bug is a missing call
or an absent guard, the thing you need is the one thing it cannot rank — that's
`grep`'s job (it finds the site the change lands in, not the string).

> **Drop this in your agent's rules:** about to change code in an indexed repo →
> `megabrain_grep`, not grep. Understanding a mechanism or copying a pattern →
> `megabrain_ask`. Reading docs → `megabrain_search` with `content: "docs"`.
> One call covers a task — never one call per sub-question.

---

## Measured, not vibes

Against [claude-context](https://github.com/zilliztech/claude-context) (Zilliz),
same repo, same 22 hand-labelled questions, both at their best:

|  | megabrain | claude-context |
|---|---|---|
| **R@1** | **0.864** | 0.818 |
| **R@5** | **1.000** | 0.909 |
| search latency | **~22 ms** warm | ~1,400 ms |
| vector store | **one SQLite file** | Milvus + etcd + MinIO |
| narrated answer | **yes** — code spliced verbatim | no (chunks) |

The golden set is ours — treat the absolutes as home-field and
[run it yourself](docs/BENCHMARKS.md): `./benchmarks/setup.sh && python benchmarks/measure.py`,
pinned commits, ground truth stated by symbol so it can't rot.

**It also learns from itself.** Every `ask` caches its walkthrough; a repeat —
even reworded — serves in ~0 ms with zero LLM (measured 27.8 s → 0.19 s), guarded
by byte-level sha rechecks so it can never describe code that changed.

**And the same index is a knowledge graph, free.** Communities, the god-node
files, the real call-path between any two files — numpy over the AST edges
indexing already extracted. `megabrain graph . --from a.py --to b.py --code`.

---

## Backends: one switch, every model lane

| provider | default model | needs |
|---|---|---|
| *(default)* OpenAI-compatible | `gemini-3.1-flash-lite` narrates · `3.5-flash-lite` judges | `OPENROUTER_API_KEY`, or a local endpoint (no key) |
| `claude` — the Claude Agent SDK | `haiku`, every lane | `megabrain[claude]` + a logged-in Claude Code |

```json
{ "models": { "provider": "claude" } }   // megabrain.json — committed, travels with the clone
```

The file beats `MEGABRAIN_CHAT_PROVIDER`, the env var beats the default. One
switch moves **every** lane — narrator, `grep --why`, judge, expander, graph
labels. ⚠️ `ANTHROPIC_API_KEY` silently beats the Claude Code login — unset it to
narrate on the subscription. Embeddings always keep their own key (Anthropic has
no embeddings API).

**Local & hybrid** — the halves are independent: embeddings see your code, the
narrator only explains what retrieval chose.

| setup | embeddings | narrator | cloud cost |
|---|---|---|---|
| hybrid, subscription | Ollama `bge-m3` | Claude Code login | **$0** beyond it |
| hybrid, cheap cloud | Ollama `bge-m3` | `gemini-3.1-flash-lite` | cents |
| fully local | Ollama `bge-m3` | Ollama `qwen3-coder:30b` | $0, air-gapped |

A loopback URL needs no key. A local model without tool support still narrates
(the `open_file` tool is retired for that conversation, announced, never silent).
Set `MEGABRAIN_ASK_CTX_CHARS=105000` for local windows — the default is sized for
the cloud. [Full local recipe →](docs/RECIPES.md#run-fully-local--no-keys-no-cloud)

---

## Commands

```bash
megabrain index  [path]                    # build/update — incremental by sha256
megabrain scan   [path]                    # census: what WOULD index, every skip named
megabrain search "retry logic" [path]      # the map, no LLM   (--full · --docs · --rerank · --expand)
megabrain ask    "how does X work" [path]  # the walkthrough, code spliced verbatim
megabrain grep   "add a retry to X" [path] # where to edit: files, symbols, line ranges
megabrain get    file.py --symbol name     # one file, or one symbol
megabrain graph  [path]                    # communities · god nodes · call paths
megabrain studio                           # web UI + JSON API on :2137
megabrain install                          # MCP into every assistant on the machine
```

Python · JS/TS · Markdown out of the box; `megabrain[languages]` adds Ruby, Go,
Rust, PHP, C, C++, Java, C#. Three runtime dependencies total (`numpy`,
`tree_sitter`, `tree_sitter_typescript`) — the thinness is a feature. Every file
in the engine is ≤100 lines and every function ≤30, **enforced by a test**, like
the rest of the hard rules: no LLM in retrieval, SQL only in `storage/`, chunks
are an exact line partition, the model never emits code.

---

## Docs

[Guide](docs/GUIDE.md) — the tour ·
[Recipes](docs/RECIPES.md) — "I want to ___" ·
[Reference](docs/REFERENCE.md) — every flag, tool, route, env var ·
[Benchmarks](docs/BENCHMARKS.md) — reproducible ·
[Architecture](ARCHITECTURE.md) — the locked rules and the experiments behind them ·
[Contributing](CONTRIBUTING.md) — best first PR: a new language

<br>

<p align="center"><sub>MIT · github.com/bernatch22/megabrain</sub></p>
