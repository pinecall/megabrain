"""What each tool SAYS it is for — the only megabrain text an agent
reads before choosing one.

Its own module for the reason every prompt in this codebase has one: the
wording IS the behaviour. These strings decide which tool an agent picks
and with what arguments, and every clause in them is a lesson from a
measured session — not documentation ABOUT the surface, the surface.
"""

from __future__ import annotations

__all__ = ["ASK", "GREP", "NODE", "SEARCH", "INDEX"]


ASK = (
         "The whole flow behind a how/where/why question, or behind the change "
         "you are about to make — narrated end to end with the REAL code "
         "spliced in at each step, verbatim from the index with true line "
         "numbers, so the CODE is never invented. The narrator OPENS whatever "
         "the retrieved chunks left unexplained (the definition a call lands "
         "on, the caller a function assumes, the test that pins the behaviour) "
         "and keeps reading until the answer is complete, so ONE call replaces "
         "a grep/Read chain — measured at 19 tool calls by hand against 6 with "
         "this, on a 1 220-file repository. Cited alongside, deterministically: "
         "the definition of every helper the prose names, and the tests that PIN "
         "what it describes — which is how a change stops breaking a test 1 600 "
         "lines away that nobody looked at. Do NOT chain one call per "
         "sub-question: one ask covers a flow. The prose is model narration, so "
         "check its claims against the code it quotes, especially on a "
         "root-cause question; retrieval itself runs no model."
)

GREP = (
         "WHERE TO LOOK for a change you are about to make — the grep "
         "replacement. Returns the files to open, the symbols inside them worth "
         "opening, each one's EXACT line range from the index, and one line on "
         "why it matters. The lanes run NO MODEL — the rows come from the index "
         "in ~50 ms, which is what lets it stand in for a grep at all; `why: "
         "true` adds one model call for a note per row plus the site whose text "
         "never contains the task's own words, and a task naming no identifier "
         "the index knows falls back to that same pass rather than answering "
         "empty. It quotes NO "
         "code on purpose — your editor opens the file anyway, so a render that "
         "pasted the body would bill you for reading it twice; the line range is "
         "what turns an open into a jump. Use it INSTEAD OF grepping a repo you "
         "have an index for: grep gives you lines that match a string, this "
         "gives you the places that matter for the task, including the ones "
         "whose text your search terms never mention. You do not need to know "
         "the FILE — but DO name the identifiers you already know, the flag you "
         "are extending or the sibling you are copying: measured, naming one was "
         "4x faster and found 3 of 4 key sites against 1 of 4 for pure prose. "
         "Pair it with `why: true` for full coverage (4 of 4, ~1 s)."
)

NODE = (
         "ONE FILE'S PLACE in the repository — the half that reading the file "
         "cannot tell you. Opening a file already shows what it imports and "
         "what it declares; nothing inside it says WHO DEPENDS ON IT, and that "
         "is the fact that decides whether your change is safe. Returns: every "
         "dependant and every dependency with the kind of each edge (import vs "
         "call), the cluster the file belongs to, its SEMANTIC TWINS — files "
         "that do the same job and never import it, which is where a migration "
         "finds the duplicate it was about to write twice — and the declared "
         "symbols with their real line ranges. No code, on purpose: your editor "
         "opens the file anyway. Use it BEFORE editing a file you already "
         "located (grep or search found it, now find out what it will break), "
         "when planning the ORDER of a refactor or a port (migrate what nothing "
         "depends on first), or to answer \"is this dead code\" — a file with no "
         "dependants and no twins usually is. `file` takes a repo-relative path "
         "or a bare filename."
)

SEARCH = (
         "ONE call that MAPS a task's whole edit surface: the files that answer "
         "it ranked, each with its best span (true line numbers) and the "
         "symbols it declares, plus the anchors a change has to touch and the "
         "tests that pin the behaviour. No code bodies by default — the map is "
         "~2 700 tokens against ~8 100 with them, and the span already tells "
         "you which lines to open; pass `bodies: true` to read the code inline "
         "instead. Search once per TASK, not once per facet. One boundary worth "
         "knowing: it ranks what EXISTS, so when the bug is a missing call or "
         "flag it shows you the site to inspect but cannot report the absence."
)

INDEX = (
         "Build or refresh a repository's index. Needed once before anything "
         "else can answer, and again only when you want changes on disk "
         "reflected — indexing is incremental by content hash, so a warm "
         "re-index costs seconds and re-embeds nothing that did not change. "
         "If a tool tells you a repository is not indexed, this is the fix."
)
