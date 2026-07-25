"""A bundle -> the code map a human or an agent reads.

Pure view: it takes the contract dicts and formats them. No store, no scoring,
no I/O — which is what lets the CLI, the MCP server and the studio share one
renderer instead of each inventing its own idea of what a result looks like.

CORE carries full code. RELATED renders as a MAP — file, best-match span,
symbols — with no code bodies. That split is measured, not aesthetic: RELATED
holds 45% of the gold files (it cannot be dropped) but ~95% of its VOLUME is
non-gold code that floods a context window. `related_code=True` restores the
inline bodies for a caller who wants them.
"""

from __future__ import annotations

from ...contracts import Bundle, Tier1File, Tier2File
from ._evidence import evidence_banner
from ._lang import lang_of

__all__ = ["render"]

REST_OF_FILE_SYMBOLS = 20
RELATED_SYMBOLS = 6


def render(bundle: Bundle, *, compact: bool = False,
           related_code: bool = False) -> str:
    """The whole bundle as markdown."""
    core, related = bundle["tier1"], bundle["tier2"]
    out = [f'# megabrain — "{bundle["query"]}"',
           f'repo `{bundle["repo"]}` · {len(core)} core files (full code) · '
           f'{len(related)} related (mapped) · {bundle["ms"]}ms\n']
    out += evidence_banner(bundle)
    out.append("## CORE\n")
    for rank, core_file in enumerate(core, 1):
        out += _core(rank, core_file, compact=compact)
    if related:
        hint = "" if related_code else " · code bodies: `--full`"
        out.append("## RELATED — best match + symbols per file · expand with "
                   f"`megabrain get <file> [--symbol NAME]`{hint}\n")
        for related_file in related:
            out += _related(related_file, compact=compact, related_code=related_code)
    return "\n".join(out)


def _core(rank: int, file: Tier1File, *, compact: bool) -> list[str]:
    """One CORE file: its matched chunks in full, then what else it declares."""
    out = [f'### {rank}. {file["file"]}  `{file["score"]:.2f}`']
    if file["neighbors"]:
        out.append(f'linked: {", ".join(file["neighbors"])}')
    covered: list[tuple[int, int]] = []
    for chunk in file["chunks"]:
        covered.append((chunk["start_line"], chunk["end_line"]))
        part = f' (part {chunk["part"]})' if chunk["part"] else ""
        out.append(f'\n**{chunk["name"] or chunk["kind"]}** '
                   f'L{chunk["start_line"]}-{chunk["end_line"]}{part}')
        if not compact:
            out += _fenced(chunk["text"], file["file"])
    out += _rest_of_file(file, covered)
    out.append("")
    return out


def _rest_of_file(file: Tier1File, covered: list[tuple[int, int]]) -> list[str]:
    """What the file declares OUTSIDE the matched spans.

    The reader is being handed a file; the parts that did not match are how
    they judge whether it is the right one, at one line each.
    """
    rest = [s for s in file["symbols"]
            if not any(lo <= s["line"] <= hi for lo, hi in covered)]
    if not rest:
        return []
    return ["\nrest of file:",
            *(f'- `{s["signature"]}` L{s["line"]}' + (f' — {s["doc"]}' if s["doc"] else "")
              for s in rest[:REST_OF_FILE_SYMBOLS])]


def _related(file: Tier2File, *, compact: bool, related_code: bool) -> list[str]:
    """One RELATED file as a map entry: why it is here, and where to look."""
    via = " ·via-graph" if file["via_graph"] else ""
    matched = f' · matched: {", ".join(file["matched"])}' if file["matched"] else ""
    doc = f' — {file["doc"]}' if file["doc"] else ""
    out = [f'### {file["file"]}  `{file["score"]:.2f}`{via}{matched}{doc}']
    best = file["best_chunk"]
    if best and not compact:
        out.append(f'**{best["name"] or best["kind"]}** '
                   f'L{best["start_line"]}-{best["end_line"]}')
        if related_code:
            out += _fenced(best["text"], file["file"])
    out += [f'- `{s["signature"]}` L{s["line"]}-{s["end_line"]}'
            for s in file["symbols"][:RELATED_SYMBOLS]]
    out.append("")
    return out


def _fenced(text: str, relpath: str) -> list[str]:
    return [f"```{lang_of(relpath)}", text.rstrip("\n"), "```"]
