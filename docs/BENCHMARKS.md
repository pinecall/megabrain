# Benchmarks

Everything here is reproducible with two commands, on public repositories, at
pinned commits. Numbers without a script are marketing:

```sh
./benchmarks/setup.sh                  # clone + index click, express, sinatra
python benchmarks/measure.py           # print the tables below
```

The question being answered is narrow and practical: **you are about to change
code in a repository you have an index for. Is `megabrain_grep` cheaper than the
`grep` you would otherwise run?**

---

## 1. The whole job, in tokens

Both arms are charged for finding the sites **and reading them**, because
discovery is the cheap half. What decides the bill is what you open afterwards.

| repo | via | discover | read | **total** | ms |
|---|---|---:|---:|---:|---:|
| click | **megabrain** | 318 | 2 245 | **2 563** | 98 |
| | grep + window | 269 | 7 386 | 7 655 | 283 |
| | grep + whole file | 269 | 67 119 | 67 388 | 283 |
| express | **megabrain** | 87 | 373 | **460** | 25 |
| | grep + window | 914 | 5 933 | 6 847 | 27 |
| | grep + whole file | 914 | 10 630 | 11 544 | 27 |
| sinatra | **megabrain** | 81 | 970 | **1 051** | 41 |
| | grep + window | 441 | 5 772 | 6 213 | 29 |
| | grep + whole file | 441 | 31 126 | 31 567 | 29 |
| **all three** | **megabrain** | 486 | 3 588 | **4 074** | |
| | grep + window | 1 624 | 19 091 | 20 715 | |
| | grep + whole file | 1 624 | 108 875 | 110 499 | |

**5.1× cheaper** than grep read tightly, **27× cheaper** than grep read the way
people actually read when a hit lands in a 3 600-line module.

Look at the `discover` column before concluding anything: it is a few hundred
tokens either way. The entire difference is `read`, and the reason is one line of
mechanism — a megabrain row carries the symbol's **exact range**, so you read
`Option.__init__` at `L2944-3023` and stop. A grep hit is one line with no
boundaries: to find where that function ends you read around it, or you read the
file.

**Latency is a tie.** Both are milliseconds (25–98 vs 27–283). Anyone selling you
speed here is selling you nothing; the saving is tokens and turns.

---

## 2. Coverage: does it return everything the change needs?

The ground truth is the set of sites you have to open to land the change,
established by **making each change by hand** — not by reading either tool's
output, which would grade the tools against themselves.

| repo | site the change needs | megabrain | grep |
|---|---|:-:|:-:|
| click | `Option.__init__` — declare the keyword argument | yes | yes |
| click | `Option.get_help_extra` — where the flag is read, or it does nothing | yes | yes |
| click | **`OptionHelpExtra`** — the TypedDict that gains a key | **yes** | **no** |
| click | `test_show_envvar` — the test to imitate | yes | yes |
| express | `res.attachment` — the sibling to copy, header for header | yes | yes |
| express | `it should Content-Disposition to attachment` — the suite to imitate | yes | yes |
| sinatra | `Sinatra.Helpers.send_file` — the sibling to copy | yes | yes |
| | **total** | **7/7** | **6/7** |

**In five of seven sites, grep ties.** If the name you are chasing is written at
every site, `grep` finds every site — and pretending otherwise would be dishonest.

The one it cannot reach is the one that matters. `OptionHelpExtra` is the
`TypedDict` the help extras flow through, and it has to gain a key for
`show_envvar_value` to appear anywhere. Its text **never contains the string
`show_envvar`** — it declares `envvars: str`. No search for the task's own words
can return it, at any level of grep skill. Miss it and you ship a flag that
parses, stores, and never shows up.

megabrain reaches it deterministically, with no model: one hop out from the sites
it already has, following the type `Option.get_help_extra` declares it returns.

---

## 3. How it works

Four lanes feed a render. **Three run no model at all** — that is the whole reason
this can stand in for `grep`, which nobody would accept if it cost a second and an
API call.

### The literal lane — what a grep would have found, resolved
The identifiers in your task, matched literally against the indexed chunk text,
then **resolved to the symbol that contains each match**. That last step is what
`grep` structurally cannot do: it turns "line 2952" into
"`Option.__init__`, `L2944-3023`", which is a place to jump instead of a place to
start looking.

Which words count as identifiers is decided by **the repository's own symbol
table**, not by shape. This was measured and the shape rule was wrong in a way
that tracked language: demanding `snake_case` or `camelCase` dropped `attachment`
from "add res.inline beside res.attachment", because it is ten characters of one
lowercase word — while the index has it at `lib/response.js:606`. One-word names
are the norm in JS and Ruby and the exception in Python, so a shape rule is a
preference for Python dressed up as a heuristic. The index is not a heuristic: it
declares `attachment` and has never heard of `beside`.

### The reference lane — one hop to the contracts those sites touch
The lane that reaches `OptionHelpExtra`. Exactly one hop, from the sites already
found to the small types and helpers they reference. One, because two starts
returning the repository.

### The import surface
What each file already has in scope, so you do not spend a read discovering that
`os` is imported.

### The model lane — opt-in, `--why` / `why: true`
One call, ~1 s, adding a note per row plus the occasional site whose text contains
nothing recognisable. Measured on click: the deterministic lanes alone returned 10
of 11 rows in **0.05 s**; adding the model took **1.3 s** — 26× — for one extra
row. So it is off by default. Retrieval never calls a model (hard rule #1).

### Two budgets, because a render that returns everything returns nothing
- **All of the implementation, a sample of the tests.** `sendFile` in express
  resolves to 47 sites: **three** implementation and **44** test cases. The three
  are where the edit goes; the tests are a pattern to imitate and you need one,
  not forty-four.
- **A one-word name gets a tighter site budget than a specific one.** `Option` is
  a class click declares, so the index vouches for it — and it resolves to 10
  implementation sites of pure noise. The one-word names that *were* the target
  resolve to one or two. Same admission, opposite verdict, decided by the count.

### It quotes no code, on purpose
Your editor opens the file to change it. A render that pastes the body has billed
you for reading it twice. This was measured the other way first: a retired tool
(`megabrain_code`) cited the bodies, and across five tasks in three languages the
retrieval was excellent and the citation was waste.

---

## 4. What the index has to get right first

A render can only be as good as what was extracted. Two measurements, both of
which were silently wrong:

**A JS test file declared nothing.** A mocha or jest suite declares its units by
*calling* a function with a label and a closure, which tree-sitter reads as an
expression statement. Express's `test/res.attachment.js` was indexed with **two**
symbols, both `require` bindings — and because a match resolves to the symbol
containing it, no row could ever land inside a test file in a JS repository.

| | symbols per file |
|---|---|
| express, before | 3.9 |
| express, after | **12.3** |
| Python (click), for scale | 16.7 |

**Build output was being indexed as source.** shipway compiles TypeScript into
`bin/`, which its own `.gitignore` declares under "# Build output" — and 122 of
its 196 indexed files were that output, so every `src/` symbol had a compiled twin
and one site returned two rows.

| repo | files indexed | dropped |
|---|---|---|
| shipway | 196 → **75** | `bin/*.js`, `bin/*.d.ts` |
| aldus | 338 → 284 | `dist-demo/`, `dist-lib-types/` |
| pinecall/sdk | 186 → 170 | `src.bkp/` — a dead snapshot competing with live code |
| click · express · sinatra | **unchanged** | nothing |

Both fixes reach an index you already built, for free: symbols cost a parse and no
embedding, so `SYMBOL_SCHEMA` re-extracts them on the next plain `megabrain
index` — measured across seven repositories, `changed=0`, **zero embedding calls**.

---

## 5. Methodology, and where it is biased

Stated so you can discount it:

- **The grep arm is charged generously.** Its `window` row assumes a reader who
  guesses a 60-line window around each hit and gets it right first time, then
  merges overlapping windows. Real readers open more. The `whole file` row is the
  other bound.
- **Tokens are `chars / 4`**, not a real tokenizer. The comparison is a ratio
  between two sets of the same source text, so any consistent divisor leaves the
  ratio intact — and a tokenizer dependency would make the benchmark unrunnable
  without it.
- **Both arms see the same corpus.** grep gets `--include` for the languages
  megabrain indexed and `--exclude-dir` for `node_modules`, so neither is
  credited or blamed for files the other never saw.
- **The ground truth is stated by SYMBOL, never by line.** Line numbers rot on the
  next upstream commit, and a benchmark whose expectations rot silently starts
  reporting whatever it still matches. `measure.py` resolves each symbol through
  the index and reports `NOT IN INDEX` rather than scoring a rename as a
  regression.
- **Three repositories, three languages, seven sites.** Small. The thresholds
  (`MAX_BARE = 6`, `MAX_TESTS = 4`) are tuned on these, so they are thresholds,
  not laws.

### What is NOT measured here

- **The agent-level A/B is n=1.** One task, click's `show_envvar_value`, two
  agents in clean clones: 20 tool calls with `megabrain_grep`, 23 with
  `megabrain_ask`, 27 with plain grep, and 7 vs 9 vs 13 calls before the first
  edit. One task is an anecdote, and the token numbers above are the claim.
- **No comparison against ripgrep, ctags, LSP or an embedding-only baseline.**
  `grep -rn` is the honest control because it is what an agent actually runs, but
  it is not the strongest possible control.

---

## 6. When plain grep is the right tool

Three cases, all real:

1. **The repo is not indexed.** `megabrain index` first, or just grep if it is a
   one-off.
2. **The file is outside the index** — a config `.json`, a lockfile, a binary.
   megabrain returns nothing for those, by construction.
3. **You know the exact string and want its lines.** One literal, one grep. The
   thing to avoid is the *chain* of greps and reads that follows, which is where
   the 5× to 27× lives.

---

## 7. `megabrain_ask`, separately

`ask` answers a different question — *how does this work* — and is measured
differently: **19 tool calls by hand against 6** on a 1 220-file repository
(anthropic-sdk-python). The mechanism is that the narrator opens the files the
retrieved chunks left unexplained and keeps reading until the answer is complete.

The threshold that makes that happen is worth stating because it is
counter-intuitive: served the **8** best chunk bodies plus a map of the rest, the
narrator opens files. Served all **30** bodies — 165 000 characters — it opened
nothing across four questions, including one that explicitly said "open this
file". More context bought less looking.

Verified correct across 9–10 repositories in 5 languages. One case worth
repeating: asked about retry jitter in the Anthropic SDK, it reported "a factor
between 0.75 and 1.0" — the actual code — rather than the code's own misleading
comment, which says "plus-or-minus half a second".

The prose is model narration; the **code is verbatim** from the index. Check the
claims against the code it quotes.
