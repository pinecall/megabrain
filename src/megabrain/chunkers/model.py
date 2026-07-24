"""The chunking data model — the one contract every chunker satisfies.

Chunks are a LINE PARTITION of their file: no gaps, no overlaps, full
coverage. That is hard rule #4 and `validate_partition` is its oracle — the
same oracle `forge` uses to accept or reject an LLM-written chunker, which is
what keeps generated code out of the index unless it is provably correct.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_BUDGET = 4000       # non-whitespace chars per chunk (cAST, arXiv 2506.15655)


def nws(text: str) -> int:
    """Non-whitespace length. The budget counts CODE, so a deeply indented
    file is not punished for its indentation."""
    return sum(1 for c in text if not c.isspace())


@dataclass(slots=True)
class Chunk:
    file: str
    kind: str                # module | class_header | class | function | method | block
    name: str | None         # qualified: "Service.handle"
    start_line: int          # 1-based, inclusive
    end_line: int            # 1-based, inclusive
    text: str
    breadcrumb: str          # repo > path > class Sig > def method(sig)
    part: str | None = None  # "2/5" for a split oversized function
    id: int = 0
    nws_chars: int = 0

    def finalize(self) -> "Chunk":
        self.nws_chars = nws(self.text)
        return self

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class Symbol:
    file: str
    name: str                # qualified: "Service.handle", "MAX_RETRIES"
    kind: str                # function | class | method | constant | …
    line: int
    end_line: int
    signature: str
    decorators: tuple[str, ...] = ()
    doc: str | None = None   # first line of the docstring

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class FileResult:
    """One file's chunking output. `parse_ok=False` still yields a valid
    partition — a file the parser choked on falls back to line windows rather
    than vanishing from the index."""

    file: str
    chunks: list[Chunk]
    symbols: list[Symbol]
    skeleton: str            # signatures + docstrings; embedded as ONE vector
    parse_ok: bool
    total_lines: int


def validate_partition(result: FileResult) -> list[str]:
    """Violations of the partition invariant — empty means perfect."""
    chunks = sorted(result.chunks, key=lambda c: c.start_line)
    if not chunks:
        return ["no chunks for a non-empty file"] if result.total_lines else []
    errs = [] if chunks[0].start_line == 1 else \
        [f"first chunk starts at L{chunks[0].start_line}, not L1"]
    errs += [f"gap/overlap between L{a.end_line} and L{b.start_line}"
             for a, b in zip(chunks, chunks[1:]) if b.start_line != a.end_line + 1]
    if chunks[-1].end_line != result.total_lines:
        errs.append(f"last chunk ends at L{chunks[-1].end_line}, "
                    f"file has {result.total_lines}")
    return errs
