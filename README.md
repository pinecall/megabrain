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

```
$ megabrain ask "how does auth work end to end" ~/repo
· retrieved in 12ms — 3 core, 14 related          ← deterministic, no LLM, already the answer
· narrating over 24 chunks…                       ← one model call, code spliced VERBATIM from disk
```

No vector DB. No containers. No services. **One SQLite file** per repo, math on
embeddings, and a hard rule with a test behind it: **the model can point at code,
it can never write it.**

Runs on a single OpenRouter key — or **hybrid**: local `bge-m3` embeddings +
your **Claude Code subscription** as the narrator, zero cloud cost beyond it
→ [Providers](#providers-recommended-and-hybrid).

> **Wiring it into a coding agent?** One fact decides everything: agents
> `Read` a file before editing it, so `search`/`ask` right before an edit puts
> the same code in context **twice**. Editing → **`megabrain_grep`** — it maps
> the edit surface (files, symbols, exact ranges) and quotes *no code*, so
> nothing is billed twice. Understanding → `ask`. Docs or the map → `search`.
> The why — and the custom-agent exception — in
> [Three verbs](#three-verbs-one-deterministic-core).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-light.png">
    <img alt="megabrain ui: retrieval lands in 25 ms across 14 files, then the cited answer streams with the real code spliced in." src="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/studio-light.png" width="900">
  </picture>
</p>

<p align="center">
  <sub><code>megabrain ui</code> — the whole engine in your browser</sub>
  <br><br>
  <a href="https://bernardocastro.dev/megabrain/demo/"><b>Try it live →</b></a>
</p>

---

## 60 seconds

```bash
pip install megabrain
export OPENROUTER_API_KEY=sk-or-...

megabrain index ~/repo                       # once — incremental by content hash after
megabrain grep "add a retry to the client" ~/repo   # where to edit, in ~50 ms
megabrain ask  "how does auth work" ~/repo   # the walkthrough, real code spliced in
megabrain install                            # wire the MCP server into Claude Code, Codex,
                                             # Cursor, Windsurf, Gemini CLI, Antigravity
```

One key gets the whole measured stack: **Perplexity `pplx-embed-v1-0.6b`** for
retrieval (won the bakeoff against pplx-4b, codestral-embed, openai-3-large,
bge-m3) and **Gemini** (`3.1-flash-lite` narrates, `3.5-flash-lite` judges).
Every default is a measurement, not a guess → [the numbers](docs/GUIDE.md#providers-and-models).

---

## Three verbs, one deterministic core

"Find me this code" is **three different jobs**, and answering all three the
same way is what makes most code-search tools feel almost useful. megabrain
ships one deterministic retrieval core and three deliverables on top of it:

| you are about to… | verb | what comes back | LLM? |
|---|---|---|---|
| **EDIT** code | `grep` | files + symbols + **exact line ranges**, zero code quoted | **no** (~50 ms) |
| **UNDERSTAND** a flow, or copy a pattern from another repo | `ask` | the walkthrough, real code **spliced verbatim** from the index | 1 call |
| read the **DOCS**, or get the map | `search` | ranked files, best span each, symbols — instant | **no** |

Plus two views over the same index: **`graph`** (the repository's structure —
who depends on whom, and how two files actually connect) and **`ui`** (all of
it in the browser).

### `grep` — when you are going to edit. This is the vital one.

You hand it the **task**, it hands you every file the change has to touch —
with the exact range to jump to:

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
`--why` adds one call for a note per row plus the site whose text never contains
the task's own words. Name the identifiers you already know — "Option has
show_envvar; add X" beats "make the help show env values", measured 4×.

> The deliverable is really a **map** of the task's edit surface — the verb may
> become `map` (`megabrain_map(task: …)`) in a future release, with `grep`
> kept as an alias.

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

Where it's the wrong tool: **right before an edit in your own repo** — see the
rule at the top. About to edit → `grep`. Need the story → `ask`.

The prose is narration; the **code is verbatim**. Check the first against the second.

### `search` — instant, zero LLM, and the docs reader

Embeddings straight from the index: the files that answer, each with its best
span (true line numbers) and its symbols. **~2,700 tokens vs ~8,100 with bodies**;
the span already says which lines to open. `--full` inlines the code,
`--docs` searches the indexed markdown — when a repo's README *is* the
API reference, this is the verb.

Two opt-in model lanes ride on top, both fail-open, neither in the core path:
`--rerank` (order — a judge reorders by the task's edit surface, never drops a
file) and `--expand` (recall — a model names the identifiers your wording missed,
the **symbol table** resolves them; a name it can't resolve is dropped, not guessed).

And it's honest about its own evidence: every bundle carries a calibrated band
(`strong` / `weak` / `none`), so an off-topic question gets *"nothing in this
repo clearly answers this"* instead of confident prose over vocabulary matches.

One honest limit: `search` **ranks what exists**. When the bug is a missing call
or an absent guard, the thing you need is the one thing it cannot rank — that's
`grep`'s job (it finds the site the change lands in, not the string).

**Building your own agent?** The double-read rule is about *stock* agents,
whose edit tools re-`Read` every file they touch. In an agent you control —
where the tool result *is* the editing context — `search` with `bodies: true`
followed directly by a patch is the leaner loop: the bundle's spans carry true
line numbers precisely so a custom harness can edit from them without a second
read. The rule isn't "never pair search with edit"; it's "never pay for the
same bytes twice."

### `graph` — the repository as a map you can walk

Built at index time from real import/call edges (plus a semantic lane for the
twins that never import each other), and it **never ranks** — that rule was
decided by experiment, not taste:

```bash
megabrain graph ~/repo                              # communities · god nodes · surprises
megabrain graph --node lib/response.js              # who imports this, who it imports
megabrain graph --from scoring.py --to narrator.py --code   # the route, with the code at each hop
```

- **Communities** — clusters of files that work together, each named by what it
  *does* (one cached model call; falls back to numbers offline).
- **God nodes** — the files everything touches, split by `in`/`out` degree so an
  orchestrator doesn't read like a load-bearing module.
- **Routes** — how two files connect, told truthfully: each hop carries the
  symbol that carries it and the real call/definition code. A route that is a
  *meeting* (`a → M ← b`) says so instead of pretending to be a flow.
- **Surprises** — two files that do the same thing and have never met: the
  duplicated mechanism no ranking ever surfaces.

### `ui` — everything above, in the browser

```bash
megabrain ui        # web UI + JSON API on :2137
```

Three tabs — **Ask** (the streamed walkthrough with the retrieval trace),
**Search** (CORE cards + the RELATED map) and **Graph** (community bubbles you
click into, routes you can *play* step by step through real code) — plus a
read-only code navigator and a scan-first "add repository" flow. `--readonly
--rate-limit N --token …` make it safe on a public box; that exact configuration
serves the [live demo](https://bernardocastro.dev/megabrain/demo/).

---

## Providers: recommended, and hybrid

Embeddings and the narrator are **independent halves**: embeddings see your
code, the narrator only explains what retrieval already chose.

**Recommended — one OpenRouter key, the measured stack:**

| lane | model | why |
|---|---|---|
| embeddings | `perplexity/pplx-embed-v1-0.6b` | won the bakeoff on both R@1 and completeness, 30–60× faster and cheaper than the losers |
| narrator | `google/gemini-3.1-flash-lite` | fastest tier at comparable quality — retrieval guarantees completeness, the model only narrates |
| judge / expander | `google/gemini-3.5-flash-lite` | obedient JSON at milliseconds; the narrator model here took 16 s for an array of integers |

**Hybrid — your Claude Code subscription narrates, local embeddings index:**

```bash
pip install 'megabrain[claude]'
ollama pull bge-m3
export MEGABRAIN_EMBED_BASE_URL=http://localhost:11434/v1
export MEGABRAIN_EMBED_MODEL=bge-m3
```

```json
// megabrain.json — committed, travels with the clone
{ "models": { "provider": "claude" } }
```

Zero cloud cost beyond the subscription: embeddings never leave the machine and
the Claude Agent SDK drives the logged-in Claude Code install for every model
lane — narrator, `grep --why`, judge, expander, graph labels. **One switch moves
all of them**; the committed file beats `MEGABRAIN_CHAT_PROVIDER`, the env var
beats the default.

⚠️ `ANTHROPIC_API_KEY` silently beats the Claude Code login — unset it to
narrate on the subscription. Embeddings always keep their own endpoint
(Anthropic has no embeddings API), which is exactly why the hybrid works.

Any OpenAI-compatible endpoint works for either half (`MEGABRAIN_EMBED_BASE_URL`,
`MEGABRAIN_CHAT_BASE_URL`); a loopback URL needs no key. More recipes →
[docs/RECIPES.md](docs/RECIPES.md).

---

## MCP: four tools, wired in one command

```bash
megabrain install       # Claude Code · Codex · Cursor · Windsurf · Gemini CLI · Antigravity
```

| tool | job |
|---|---|
| `megabrain_grep` | the edit surface: files, symbols, exact line ranges — no model |
| `megabrain_ask` | the narrated walkthrough, code spliced verbatim |
| `megabrain_search` | the map (or the docs): files, best spans, symbols — no model |
| `megabrain_index` | build/refresh — incremental, seconds when warm |

Four on purpose: every tool costs the calling agent context and a routing
decision. A fifth, `megabrain_node`, shipped and was **removed** after an A/B
on two real fixes — it answered who imports a file, which the graph already
serves over CLI and HTTP, and on the tasks that decided it that was either the
wrong question or a shortcut that skipped the context where the right
abstraction lived. The schemas are **generated from the typed contracts**, so a parameter
cannot reach the wire without existing in the dispatch — and every description
is a lesson from a measured session, because it's the only documentation the
agent ever reads.

---

## Commands

```bash
megabrain index  [path]                    # build/update — incremental by sha256
megabrain scan   [path]                    # census: what WOULD index, every skip named
megabrain search "retry logic" [path]      # the map, no LLM   (--full · --docs · --rerank · --expand)
megabrain ask    "how does X work" [path]  # the walkthrough, code spliced verbatim
megabrain grep   "add a retry to X" [path] # where to edit: files, symbols, line ranges
megabrain get    file.py --symbol name     # one file, or one symbol
megabrain graph  [path]                    # communities · god nodes · routes (--from/--to --code)
megabrain ui                               # web UI + JSON API on :2137
megabrain install                          # MCP into every assistant on the machine
```

Every verb resolves the repo upward like git — run it from any subdirectory.
Python · JS/TS · Markdown out of the box; `megabrain[languages]` adds Ruby, Go,
Rust, PHP, C, C++, Java, C#.

---

## The rules the engine is built on

These aren't a style guide — each one is **enforced by a test**, and several
were decided by experiments whose numbers live in [ARCHITECTURE.md](ARCHITECTURE.md):

1. **No LLM in the retrieval path.** A test walks the imports. An LLM in
   retrieval was measured four ways and cost completeness every time.
2. **Completeness beats ordering.** The recall floors only ever *add* files;
   a change that lowers `bundle_full` doesn't merge.
3. **The graph never ranks.** PageRank-as-ranking dropped Acc@1 from 0.91 to
   0.73 — it supplies candidates and evidence, nothing else.
4. **Chunks are an exact line partition.** No gaps, no overlaps, checked by an
   oracle — the same one that gates generated chunkers.
5. **The model never emits code.** It cites `[[k:lo-hi]]`; the engine splices
   the real bytes from the index. Feed it fabricated code and not one line
   survives — there's a test for that too.

Three runtime dependencies total (`numpy`, `tree_sitter`,
`tree_sitter_typescript`) — the thinness is a feature. Every file ≤100 lines,
every function ≤30, SQL only in `storage/`, all of it enforced the same way.

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
