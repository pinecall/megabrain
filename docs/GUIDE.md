# Guide

The tour, front to back. Read it once and you'll know everything megabrain does.
Looking for a specific flag? → **[Reference](REFERENCE.md)**. A specific goal? →
**[Recipes](RECIPES.md)**. Why it's built this way? → **[Architecture](../ARCHITECTURE.md)**.

1. [Install and your first answer](#1-install-and-your-first-answer)
2. [The two ways to ask](#2-the-two-ways-to-ask)
3. [The studio](#3-the-studio)
4. [Map the repo with the graph](#4-map-the-repo-with-the-graph)
5. [It remembers — the flow cache](#5-it-remembers--the-flow-cache)
6. [Wire it into your coding agent](#6-wire-it-into-your-coding-agent)
7. [Teach it your file types](#7-teach-it-your-file-types)
8. [Tuning](#8-tuning)

Every verb reads **`<query> [path]`** — the question first, the path second, and the path
defaults to `.`. It may be any sub-path inside an indexed repo; megabrain finds the root
from `.megabrain/` upward and scopes retrieval to files under it.

---

## 1. Install and your first answer

```bash
pip install megabrain                 # core: Python · JS/TS · Markdown
pip install 'megabrain[languages]'    # + Ruby · Go · Rust · PHP · C · C++ · Java · C#
```

megabrain needs **embeddings** (always) and, for `ask`, a **chat model**. They are
independent knobs — you can mix cloud embeddings with a local narrator, or the reverse.
Both talk plain **OpenAI-compatible HTTP** over urllib; there is no SDK in the dependency
list, and a loopback URL needs no key at all.

### The recommended setup

**One OpenRouter key.** The defaults are the measured-best set, so there is nothing to
configure:

```bash
export OPENROUTER_API_KEY=sk-or-...

megabrain index ~/repo                          # once; incremental after
megabrain ask   "how does auth work" ~/repo
```

| | model | why it's the default |
|---|---|---|
| **embeddings** | `perplexity/pplx-embed-v1-0.6b` | **the best measured for code recall.** A head-to-head bakeoff beat pplx-4b, codestral-embed, openai-3-large and bge-m3 — R@1 **0.864**, bundle_full **0.955**. Perplexity-direct and via-OpenRouter score identically, so the proxy costs nothing. |
| **narration** | `google/gemini-3.1-flash-lite` | **the fastest and cheapest tier** at the quality of models several times its price. `ask` is output-bound, so this is the knob that decides how long you wait. |
| **the judge** | `google/gemini-3.5-flash-lite` | a separate constant, because the job is not the same — see [Providers and models](#providers-and-models). |

That combination is the one to beat: best retrieval quality, fastest narration, ~$0.002 to
index a repo and fractions of a cent per ask. Everything below is a deliberate trade-off
away from it.

### The alternatives

| instead of… | do this | trade-off |
|---|---|---|
| the cloud entirely | [run fully local](RECIPES.md#run-fully-local--no-keys-no-cloud) | $0, nothing leaves your machine; the best local embedder ties the cloud on completeness and ranks the #1 slot lower (R@1 0.773 vs 0.864) |
| the default price | `export MEGABRAIN_ASK_MODEL=qwen/qwen3-coder` | ~half the cost, ~2× slower, open weights |
| a per-shell setting | commit a [`megabrain.json`](REFERENCE.md#config-files) | the whole team narrates with the same model, because the config travels with the repo |

The index is one SQLite file at `~/repo/.megabrain/db.sqlite`. It is **incremental by
sha256**, so a re-index costs seconds and re-embeds only what changed — and changing the
embed model forces a full re-embed on the next `index`, so vectors can never silently
mismatch. There is no background refresh: `megabrain index` is the one step that reads
disk, and a file it has not seen since you edited it is served with a **stale** marker
rather than pretended to be current.

Full bakeoff numbers: [Architecture §8](../ARCHITECTURE.md#8-evidence-where-the-numbers-live).

---

## 2. The two ways to ask

Everything else in megabrain is built on these two verbs — plus the graph, which reads the
same index. All three in one picture:

<p align="center">
  <img src="https://raw.githubusercontent.com/bernatch22/megabrain/master/assets/ask-agents.svg" alt="Three acts. One, search: no-LLM retrieval ranks the chunks, then the LLM rerank strikes the vocabulary-only matches and reorders what survives — app.py's prune function climbs from fourth to second, past two higher-scoring chunks, leaving the score column deliberately out of order. Two, ask: a broad question fans out into three parallel sub-agents, one synthesis merges their cited answers with the verbatim code spliced in, and the finished workflow lands in the flow cache. Three, graph: a path query between two files reports that they never call each other, names the file that bridges them, and labels every hop with the function that carries it." width="900">
</p>

<p align="center">
  <sub><b>search</b> ranks the signal, then the rerank drops the vocabulary-only look-alikes
  <b>and reorders what survives</b>.
  <b>ask</b> fans a broad question into parallel sub-agents and splices verbatim code into
  the synthesis. <b>graph</b> reports that two files never call each other and names the
  one that bridges them.</sub>
</p>

### `search` — the code, no LLM

```bash
megabrain search "retry logic" ~/repo             # the MAP: CORE + RELATED, no code bodies
megabrain search "retry logic" ~/repo --full      # …with the code inline
megabrain search "retry logic" ~/repo --rerank    # + one cheap judge call, reorders only
megabrain search "retry logic" ~/repo --expand    # + one call that widens the pool
megabrain search "how to deploy" ~/repo --docs    # the indexed markdown instead of the code
```

Pure retrieval: your question is embedded and matched by vector similarity — one HTTP
round trip for the query vector, then milliseconds of numpy. Free, and it never depends on
a model being up.

**The MAP is the default.** Measured on a real bundle, the map costs **2 660 tokens** where
CORE-with-bodies costs **8 135**, and it carries what a reader needs to decide: the file,
its best span with true line numbers, and the symbols it declares. The code is one `--full`
away, or one `megabrain get` away for a single file.

**`search` is code OR docs, never a blend** — `--code` and `--docs` each confine retrieval
*before* scoring; omit both and they compete. Blending them sounds harmless and isn't: with
both in one index, a large README wins prose-shaped questions and buries the implementation
it describes (on sinatra, `README.md` took the top slot from `lib/sinatra/base.rb` for
*"how are routes defined and dispatched?"*).

**Which one you want depends on which side of the API you're standing on.** `--docs` is
for *consuming* something: you're building an app on a framework and need its documented
usage now — what to call, in what order, the way its authors wrote it down. The default is
for *working on* something: contributing to Rails, or any internal repo where the docs are
thin, stale, or were never written and the source is the only truth. That second case is
most of them.

The distinction also tells you which one to distrust. Docs describe intent and go out of
date silently; code is what actually runs. When an answer from `--docs` contradicts one
from the default, the default is right and you have just found a stale doc.

**`--rerank`** adds one buffered model call on top. Retrieval is recall-safe by design, so
files that merely *share vocabulary* with your query (tests, eval scripts) survive — cosine
can't tell "implements scoring" from "tests scoring". The judge sees a compact view (ids,
spans, names, no bodies) and returns the relevant ids, ordered; the engine then reorders
its **own verbatim chunks**. The model selects, it never writes, and **it never drops a
file**. Fail-open in every branch — no key, timeout or junk reply returns the deterministic
bundle untouched.

**`--expand`** buys RECALL where `--rerank` buys ORDER. The judge can only reorder what
cosine found; when the answer never enters the pool, no reordering rescues it. So one call
asks a model to name the **identifiers your wording missed** — the method or class the code
itself uses — and the **symbol table** resolves them to the files that define them. It
loops, up to three rounds, stopping as soon as a round adds nothing. Only ever ADDS.

*Why the symbol table and not another search.* Asked what sinatra's early-exit mechanism
was missing, a model named exactly the right identifiers — `halt`, `pass`, `redirect`,
`error`. Feeding those back through the **embedder** found none of the ground truth, in any
arrangement: query+terms returned `CHANGELOG.md` and two rack-protection middlewares, terms
alone returned five more of the same, one-search-per-term returned 25 files and none of the
answer. A bare identifier is a terrible sentence, and a sentence is what an embedding space
places. `symbols.find("halt")` answers with one hit and the line it is defined on. A name
the table cannot resolve is therefore **dropped, not guessed at**.

> **Measured safe, not yet measured useful.** Across 15 hand-verified sinatra questions ×3
> runs each, expansion never lost a case — and never rescued one either, because the
> deterministic baseline already held the ground-truth file in **15/15**. That is a finding
> about the test set as much as the lane. Reach for `--expand` when the answer plainly is
> not in the list; it is off by default because an unproven optimisation should cost nobody
> a model call.

### `ask` — the repo, explained

```bash
megabrain ask "how does auth work end to end" ~/repo
megabrain ask "how do the docs describe setup" ~/repo --docs   # markdown instead of code
megabrain ask "how does X work" ~/repo --quiet                 # the answer only, no trace
```

One model call narrates the answer and cites code as `[[k]]` or `[[k:705-731]]`; **the
engine replaces each citation with the verbatim block from disk**. The model can only
*point* — which is why `ask` cannot hallucinate a line of code. The **prose around the code
is still narration**: when it matters (root-cause hunts), check its claims against the
spliced code, which is the ground truth.

The narrator can also **open files** the retrieved chunks left unexplained — the definition
a call lands on, the caller a function assumes, the test that pins the behaviour — and keeps
reading until the answer is complete. That is the loop that replaces a grep/Read chain:
measured at 19 tool calls by hand against 6 through `ask`, on a 1 220-file repository.

**Asking about a bug? Name the state to track, not just the symptom.** Measured on a real
Rails bug (a value wiped by an `ensure` racing a deferred block): every narrator model,
weak or strong, invented a wrong mechanism for *"why is the retry enqueued immediately?"* —
while *"where along that path could `scheduled_at` be lost?"* got the correct trace. The
symptom tells the model what to explain; the named state tells it what to follow.

On a **broad** question `ask` becomes its own multi-agent system. A no-LLM classifier reads
the *shape* of the retrieved bundle — several core files? candidates spread across
subsystems? — and if it's broad, a planner splits the bundle into scoped slices (up to
`MEGABRAIN_MAX_AGENTS`, default 4). Parallel sub-agents explain their slice, each able to
call retrieval tools on demand, and a synthesizer merges them into one walkthrough with the
same global citations. Every stage fails open to the single-agent path.

Retrieval is emitted as an event **before any model runs**, so a caller that reads the file
list and stops has lost nothing. On the CLI that trace goes to stderr and the walkthrough
to stdout — `megabrain ask … > answer.md` keeps the file clean.

### Which one?

| your question | use | why |
|---|---|---|
| "**how/why** does X work" — a flow, cross-file behaviour | **`ask`** | you want the connected story; retrieval gives you the pieces, ask assembles them |
| "**this is broken, find the cause**" — a bug you can already reproduce | **`search --rerank`** | you need the colliding spans on one screen, not a theory about them; see below |
| "give me the **code worth reading**" — you'll reason over it yourself | **`search --full`** | ranked, *with the code*, **zero LLM cost** |
| "**where** is Y" — locate a symbol or handler | **`search`** | free and instant |
| "I am about to **change** this" | **`grep`** | files, symbols and exact line ranges — [see the README](../README.md#why-grep-quotes-no-code-on-purpose) |

**Debugging a reproducible bug? Reach for `search --rerank`, not `ask`.** Measured on
rails/rails#57197: the judge cut 33 chunks to the exact 3 files the fix touched, in ~760 ms
and one cheap call — versus ~9.5 s and a fan-out for `ask`. Both found the right code; only
`ask` wrapped it in prose, and prose is the one surface that can be wrong. When two spans
collide, putting them side by side *is* the explanation.

Never chain `search` + your own summarization to imitate `ask`: ask's splice guarantees the
code shown is verbatim, a summary doesn't.

---

## 3. The studio

```bash
megabrain ui                    # every repo you've indexed → http://127.0.0.1:2137
megabrain ui --port 8080        # …anywhere else
```

*(Screenshot on the [README](../README.md) — this section is the tour behind it.)*

TypeScript built with esbuild into the package, so an install serves the UI with no node
toolchain; one stdlib HTTP server hosts the UI and the JSON API on the same port, and
loopback-only by default. **Three tabs:**

- **Ask** — the retrieval bar appears *before* the model has said anything, then the
  walkthrough streams in with the real code spliced as it lands. A repeat of a cached
  question is served from the [flow cache](#5-it-remembers--the-flow-cache) with no model
  call; a *related* one is attached as context. **Starter chips** sit under the bar —
  [every repo gets them](#starter-questions).
- **Search** — **CORE** as expandable file cards, **RELATED** as a compact map. The card is
  closed by default, which is the design's answer to the same measurement the renderer
  makes: RELATED holds 45% of the gold files but ~95% of its volume is code nobody asked
  for, so the code is one click away rather than on screen. A **judge toggle** turns the
  rerank on per query.
- **Graph** — [the knowledge graph](#4-map-the-repo-with-the-graph) on a live canvas:
  community bubbles, one community expanded, and a route between two files with a
  step-through of the call→definition chain.

**Code or docs** sits on both the Ask and the Search bar as a scope picker. It confines
retrieval before scoring — the studio's face of `--code` / `--docs`. Search defaults to
letting them compete; Ask defaults to code, because a walkthrough diluted with prose
explains the documentation instead of the mechanism.

**The code navigator** opens over any view. Click any file — a search card, a graph node —
and the whole file opens: real bytes, syntax-highlighted, scrolled to the exact line.
**Every identifier with a resolvable definition is a link** (receiver-aware and
import-anchored: `Path(x).resolve()` links to nothing because it's stdlib, while
`store.stats()` jumps to store.py).

**Adding a repo censuses it first** — you see exactly what will index and what's skipped
and *why* (excluded · gitignored · too-big · unreadable), plus the file types this build
cannot read at all, then watch a live progress bar index it file by file.

### Starter questions

Every indexed repo gets one-click chips under the ask bar. The server picks the best
source it has and labels the row honestly:

| source | where it comes from |
|---|---|
| `file` | the repo committed **`queries`** in its [`megabrain.json`](REFERENCE.md#config-files) — authored intent wins |
| `derived` | deterministic, no-LLM questions over the repo's most depended-on files and the names they declare |
| `none` | an index with nothing prominent enough to ask about |

Click through them once and every one of those answers is [cached](#5-it-remembers--the-flow-cache),
so the chips then serve instantly with no model call.

→ **[Server flags and the JSON API](REFERENCE.md#http-api)** ·
**[Run a public read-only demo](RECIPES.md#run-a-public-read-only-demo)**

---

## 4. Map the repo with the graph

```bash
megabrain graph ~/repo                                    # the map
megabrain graph ~/repo --node "the scoring pipeline"      # one file — concepts resolve by embedding
megabrain graph ~/repo --from scoring.py --to narrator.py # how two files connect
megabrain graph ~/repo --from a.py --to b.py --code       # …with the real code at each hop
```

Every dot is a file. **Colour** = its community (files that import/call each other or talk
about the same thing). **Glow** = a god node, one of the most-connected files. A **solid
line** is a real import/call edge from the AST; a **dashed line** is a *semantic* edge —
two files talking about the same thing with no code link between them.

None of this costs extra at index time; it's derived from what indexing already stored, in
milliseconds. The **only** model touch is one cached call that *names* the communities
(`--no-labels` skips it, fully offline).

`--node` takes a path, a filename tail, or **a concept** — the ladder goes from certain to
inferred (exact path → filename → meaning against the skeleton vectors retrieval already
built) and stops at the first rung that answers.

A route names the **symbols that carry each hop**, not just which files connect — and it
tells you when the two files are not a chain at all:

```
$ megabrain graph . --from search/scoring/pipeline.py --to ask/narrator.py
search/scoring/pipeline.py
└→ search/bundle/assemble.py  [call]  · score_chunks, search_with_state
  └→ ask/narrator.py          [call]  · narrate

! not a call chain: the two files MEET at ask/ask.py — both ends call into it
```

That footer exists because an indented arrow diagram reads like a flow that does not exist.
`scoring → ask ← narrator` is a *meeting*, not a path, and saying so is the difference
between a map and a guess.

### What it's actually good for

1. **Landing on an unfamiliar repo** — communities tell you the subsystems, god nodes tell
   you the reading order, sizes tell you where the mass is.
2. **Impact estimation** — about to touch a god node? Its degree is the blast radius, and
   `--node` lists exactly who depends on it, both directions.
3. **Finding duplication** — "twins that never met" (≥0.85 similar, different communities,
   *no* code link) is a free near-duplicate detector. On graphify it surfaced every
   generated skill file paired with its golden twin: content maintained in two places,
   found automatically.
4. **"How do these two even relate?"** — `--from/--to` answers with the real chain, with a
   semantic hop when there is no code path, or with the honest "they only meet".

Coverage: Python · TS/JS have structural edges from their own extractors; the other
languages index and chunk without a dependency graph for now.
→ **[Thresholds and knobs](REFERENCE.md#graph)**

---

## 5. It remembers — the flow cache

**On by default, and it needs no commands.** Every `ask` synthesizes a cross-file workflow
("VAD detects speech → `TurnController.on_vad_start` → cancel TTS"). That used to be thrown
away. Now it's stored in the same SQLite file, and the next related question — even worded
completely differently — retrieves the whole workflow at once.

| ask | time | LLM |
|---|---|---|
| first time | 27.8 s | pays once, caches |
| repeated, even reworded | **0.19 s** | **none — served from cache** |
| that question **plus another** | full narrate | the cache doesn't *cover* it — attaches as context, answers both |
| after a cited file changed | 21.9 s | sha recheck refuses the stale answer, narrates fresh |

**Three guards, because a cache that lies is worse than no cache:**

- **It can never describe changed code.** A flow records the sha256 of every file it cites,
  and serving re-checks each one **byte-for-byte at that instant**.
- **It can never answer half your question.** Resembling a cached question isn't enough —
  the cached one has to *cover* it. Cosine is symmetric, but "may I reuse this?" isn't: a
  compound question that *contains* a cached one scores ~1.0 against it. Ask *"how do
  filters run around a handler, **and how is a route defined?**"* with both halves cached
  separately, and the naive answer is the filters walkthrough alone with the routing half
  silently dropped. So serving also requires that nearly every content word of your
  question already appear in the cached one.
- **A near-match is context, not the answer.** Below the serve threshold a flow is attached
  to the bundle as **non-citable** context and the narrator writes fresh, splicing real
  code from disk regardless.

The hard rule holds: the model and the embed happen at *ask* time (the write path); the
read path is pure cosine and file hashes, so nothing under retrieval ever calls a model.
Flows only *add* their source files to the bundle when missing — they never displace real
files. Everything lives in the repo's own `.megabrain/db.sqlite`: commit it and the team
inherits the cache, or leave it gitignored and let each machine build its own.

→ **[Turn a repo into a team knowledge base](RECIPES.md#turn-a-repo-into-a-team-knowledge-base)**

---

## 6. Wire it into your coding agent

```bash
megabrain install            # detects + registers; --list to preview, --remove to undo
```

```text
Registered megabrain in 3 platform(s):
  ✓ Claude Code  registered   ~/.claude.json
  ✓ Codex        registered   ~/.codex/config.toml
  ✓ Antigravity  registered   ~/.gemini/antigravity/mcp_config.json
  · Cursor       skipped (not installed)
```

Supported: **Claude Code · Codex · Antigravity · Cursor · Windsurf · Gemini CLI**. It only
ever writes the `megabrain` key — your other MCP servers, your unrelated settings and (in
Codex's TOML) your comments are left alone — and it pins the entry to the interpreter
megabrain is installed in, so re-running it repairs a config that drifted to an old
checkout. `--platform NAME` writes just one, even if it was not detected.

By hand, if you would rather:

```bash
claude mcp add megabrain -- python3 -m megabrain.transports.mcp
```

```json
{ "mcpServers": { "megabrain": { "command": "python3",
                                 "args": ["-m", "megabrain.transports.mcp"] } } }
```

Your agent gets **four** tools, and the smallness is the point: every tool costs it context
and a routing decision, and reading one span is the host's own Read job.

| tool | when the agent reaches for it |
|---|---|
| **`megabrain_grep`** | **it is about to change code** — files, symbols, exact line ranges; the lanes run no model |
| **`megabrain_ask`** | any "how/why does X work", or a pattern to copy out of another repo |
| `megabrain_search` | the map, or a repo's docs (`content: "docs"`) |
| `megabrain_index` | make a repo answerable, or refresh it |

→ **[Every parameter](REFERENCE.md#mcp-tools)** ·
**[The one rule that makes it pay off](RECIPES.md#give-your-coding-agent-the-whole-repo)**

---

## 7. Teach it your file types

`.toml`, `.astro`, `.proto`, a private DSL — anything outside the built-in languages is
invisible to retrieval. The extension point is a **Protocol**, not a fork: write an object
of the right shape and pass it in.

```python
from megabrain import index_repo

class TomlStrategy:
    exts = (".toml",)

    def parse(self, relpath: str, source: str): ...        # -> Parsed
    def edge_context(self, sources: dict[str, str]): return None
    def edges(self, relpath, source, context): return None  # no dependency graph

index_repo("~/repo", strategies=[TomlStrategy()])
```

Injected strategies are consulted **before** the built-ins, so a caller can also override a
shipped extension and not just claim an unhandled one. The one hard requirement is checked
rather than trusted: your chunks must form an **exact line partition** of the file — no
gaps, no overlaps, full coverage — and `validate_partition` reports any file where they do
not, per index run.

> **Chunking an already-covered type "better" is a different job, and it loses.** Six
> attempts, six losses — read [the chunk budget](#the-chunk-budget) before reaching for it.

---

## 8. Tuning

### Providers and models

One adapter, `providers/chat/openai_compat.py`, urllib only: OpenRouter, a provider's
native API, or a local runtime all speak the same shape. `MEGABRAIN_CHAT_BASE_URL` points
it anywhere; a loopback URL needs no key.

```bash
export MEGABRAIN_ASK_MODEL=qwen/qwen3-coder       # the narrator
export MEGABRAIN_RERANK_MODEL=…                   # the judge, independently
```

Better than either: commit them, so the whole team gets the same walkthroughs.

```json
{ "models": { "provider": "openrouter",
              "narrator": "google/gemini-3.1-flash-lite",
              "rerank":   "google/gemini-3.5-flash-lite" } }
```

`provider` picks the BACKEND for every model lane at once: `claude` narrates through the
Claude Agent SDK (default model `haiku`, extra `megabrain[claude]`), anything else keeps
the OpenAI-compatible endpoint. The committed file beats `MEGABRAIN_CHAT_PROVIDER`.

| ask model | one ask | ≈ cost | notes |
|---|---|---|---|
| `google/gemini-3.1-flash-lite` *(default)* | fastest | ~$0.007 | the narration default |
| `google/gemini-3.5-flash-lite` | fastest | ~$0.011 | the **judge** default — see below |
| `qwen/qwen3-coder` | ~14 s | **~$0.0035** | cheapest, broader citations, open weights |

**Why two constants and not one.** Narration reasons about a flow in prose; the judge emits
a short id array. Measured over 20 mined cases × 3 repetitions on identical candidate
lists:

```
3.5-flash-lite   recall 19/20/19 · rank1 19/19/19 · kept 2,2,2 · ~1.13s
3.1-flash-lite   recall 19/19/19 · rank1 19/19/19 · kept 3,2,3 · ~1.28s
```

Equal recall and ordering; 3.5-lite prunes one file tighter, every repetition. And **bigger
is worse**, also measured: reasoning models return empty (thinking eats the 300-token cap),
some truncate the JSON, and plain `gemini-3.5-flash` — five times the price — failed open at
5.6 s. The judge wants an obedient fast model, not a smart one. Sharing one model between
the two jobs is what made an earlier judge take sixteen seconds.

→ **[Cut the cost, or make it faster](RECIPES.md#make-ask-cheaper-or-faster)** ·
**[Run fully local](RECIPES.md#run-fully-local--no-keys-no-cloud)**

### The chunk budget

megabrain merges small syntax units up to **4000 non-whitespace chars**. It's the most
important knob, and the honest guidance is: **leave it alone.**

On the only human-verified query set, 4000 wins — R@1 **4000 = 0.86**, 2000 = 0.82,
8000 = 0.77. Bigger dilutes the signal; smaller fragments the evidence. Tighter chunks
*do* help navigation (fewer lines to read) but **lower retrieval quality**, because the
4000 merge concentrates a file's evidence and that is what wins the ranking. Five
"smarter" alternatives were measured and all lost.

**It looks broken by language, and it is not.** Count the share of chunks that are a
function or a method and the spread is alarming — Python **49%**, TypeScript **14 / 11 /
2%**, Ruby **0%** (147 sinatra files, not one method chunk). The cause is real and simple:
a file *smaller than the budget* is never opened at all, so `link_header.rb` (2 667
non-whitespace chars, five methods) is **one chunk**. Ruby and TS files are small, Python
files are not. Lowering the budget moves TS (4% → 27%) and does not move Ruby, because for
Ruby the seam is never reached — and `merge` folds the pieces straight back up to the same
4 000 anyway. *The budget governs both halves.*

That reads like a bug, so it was measured rather than fixed: sinatra re-indexed with every
declared member opened (285 → **1 342** chunks, leading comments attached to their method,
partition still exact), scored on 16 hand-verified questions. **Better on 2, worse on 5,
one truth file lost entirely.** Same repo, same queries, same retrieval code. The sixth
"smarter chunking" attempt, and the sixth to lose, for the reason above: the ranking fuses
a file's chunks, so one rich vector per small file *is* the signal, and twelve thin ones
dilute it. **Zero method chunks in Ruby is not costing you recall — it is what buys it.**

### Scoping

```bash
megabrain ask "how does login work" ~/repo/src/auth      # scope to a sub-folder
megabrain search "retry logic" ~/repo --path-filter src/ # …or filter explicitly
```

Any path inside an indexed repo works — megabrain finds the root and scopes retrieval to
files under your path. Over MCP, pass `scope_path`. Scoping **excludes** everything
outside it, so scope to a package *root*, never to its `src/` or `lib/` subfolder, or you
cut away the package's tests — usually the spec of what you asked about.

→ **[Every environment variable](REFERENCE.md#environment-variables)**
