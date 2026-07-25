"""A bundle -> the code map a human or an agent reads.

Pure view: it takes the contract dicts and formats them. No store, no scoring,
no I/O — which is what lets the CLI, the MCP server and the studio share one
renderer instead of each inventing its own idea of what a result looks like.

The DEFAULT is the map: every file with its best-matching span and the symbols
it declares, no bodies anywhere. Measured on a real bundle, that is ~2 700
tokens against ~8 100 with CORE bodies inlined — and the span already names the
lines to open, so the code is a flag away rather than in the way.

`compact=False` inlines CORE's bodies; `related_code=True` adds RELATED's too.
That ordering is itself measured: RELATED holds 45% of the gold files (it cannot
be dropped) but ~95% of its VOLUME is non-gold code that floods a window.
"""

from __future__ import annotations

from ...contracts import Bundle, Tier1File
from ._entries import related_entry, rest_of_file
from ._evidence import evidence_banner
from ._fence import fenced

__all__ = ["render"]

def render(bundle: Bundle, *, compact: bool = False,
           related_code: bool = False) -> str:
    """The whole bundle as markdown."""
    core, related = bundle["tier1"], bundle["tier2"]
    # The header states what this render ACTUALLY carries. It said "full code"
    # unconditionally, which became a lie the moment the map turned into the
    # default — and a header that misdescribes its own body is how a reader
    # concludes the code is missing rather than not asked for.
    carrying = "with code" if not compact else "mapped"
    out = [f'# megabrain — "{bundle["query"]}"',
           f'repo `{bundle["repo"]}` · {len(core)} core files ({carrying}) · '
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
            out += related_entry(related_file, compact=compact,
                                 related_code=related_code)
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
            out += fenced(chunk["text"], file["file"])
    out += rest_of_file(file, covered)
    out.append("")
    return out
