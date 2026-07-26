"""Every consecutive HOP between two files, checked against the graph.

MEASURED. Asked about a barge-in mechanism, the narrator wrote that one file
"delegates the actual cleanup to the session layer by calling" a function in
another — real code, quoted verbatim, genuinely about interruption handling.
But the two files share ZERO edges, of any kind, either direction; the named
function has no caller anywhere in the repository. The graph the indexer
already built knew this for free, and knew the REAL relationship too: the file
that actually constructs the caller shows both an import and a call edge to it.

Rerank was the first fix considered and rejected: both files were legitimately
RELEVANT to the question, so a better-ordered candidate list still contains
both. The failure is not which files were shown — it is an unsupported claim
about how two shown files relate, and that is a graph fact, not a ranking one.

Scoped to CONSECUTIVE citations, not every pair: a correct walkthrough of
A -> B -> C has no edge A-C even when every step is right, because the graph
only records DIRECT relations. Checking the hop the narration itself makes —
the file just cited, into the very next one — is what "delegates to" or
"calls" actually asserts.
"""

from __future__ import annotations

from pathlib import Path

from ...storage import Store
from ...storage.model import ChunkMeta
from ..citing._quote import CITATION as PATH_CITATION
from ..citing.citations import CITATION as CHUNK_CITATION
from ..citing.citations import parse_citations

__all__ = ["unlinked_hops"]


def unlinked_hops(raw: str, candidates: list[ChunkMeta], root: Path | None) -> str:
    """A note for every narrated hop the graph has no edge for.

    Without a `root` there is no graph to check against — the multi-agent path
    narrates that way — so this is empty rather than an error, the same
    contract `widen` and the final quoting pass hold to.
    """
    if root is None:
        return ""
    with Store(root) as store:
        return _checked(store, raw, candidates)


def _checked(store: Store, raw: str, candidates: list[ChunkMeta]) -> str:
    files = _file_sequence(raw, candidates)
    pairs = dict.fromkeys(
        (a, b) for a, b in zip(files, files[1:])
        if a != b and b not in store.graph.neighbors(a))
    if not pairs:
        return ""
    lines = "\n".join(f"- `{a}` -> `{b}`" for a, b in pairs)
    return ("\n\n## Not in the import/call graph — this step is UNVERIFIED\n"
            "The index has no import, call or pin edge, in either direction, between these "
            "files at the point the walkthrough moves from one to the other. The extractor "
            "resolves a call through an import, a dotted module path, or an attribute that "
            "binds to one file repo-wide — so a hop listed here is one none of those "
            f"explain, and worth checking before you rely on it:\n{lines}")


def _file_sequence(raw: str, candidates: list[ChunkMeta]) -> list[str]:
    """Every cited file, chunk or path form, in the order the prose cites them.

    Position, not citation kind, decides the order: a hop from a `[[k]]` chunk
    straight into a `[[path:lo-hi]]` opened file is still a hop the narration
    made, and the two forms are interleaved in the raw text as the model wrote
    them.
    """
    hits: list[tuple[int, str]] = []
    for match in CHUNK_CITATION.finditer(raw):
        for citation in parse_citations(match.group(0)):
            if 0 <= citation.index < len(candidates):
                hits.append((match.start(), candidates[citation.index].file))
    for match in PATH_CITATION.finditer(raw):
        hits.append((match.start(), match.group(1).strip()))
    hits.sort(key=lambda hit: hit[0])
    return [file for _, file in hits]
