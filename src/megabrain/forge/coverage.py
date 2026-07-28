"""The coverage forge: detect → generate → validate → install → reindex.

The model writes code exactly once, at forge time, gated by the oracle — the
retrieval path stays model-free (hard rule 1) and index time runs only vetted,
trusted code. forge fails LOUD, unlike ask's fail-open narration: it is an
explicit user action, and a silent no-op would read as "nothing to forge".
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..indexing.trust import STRATEGY_DIR, trust_file
from ._backend import Generate, backend_generate, extract_code
from .detect import Candidate, detect
from .oracle import validate_strategy

__all__ = ["forge", "install", "ATTEMPTS"]

ATTEMPTS = 3


def forge(root: Path | str, *, ext: str | None = None, dry_run: bool = False,
          attempts: int = ATTEMPTS, model: str | None = None,
          generate: Generate | None = None,
          embedder: Any = None) -> dict[str, Any]:
    """One report over every uncovered extension (or just `ext`).

    `generate` is prompt -> raw model text, injectable so the whole loop is
    testable offline; the default resolves the repository's chat backend and
    raises without a credential — loud, because the caller asked to forge.
    """
    base = Path(root).resolve()
    started = time.time()
    candidates = detect(base)
    if ext:
        want = ext if ext.startswith(".") else f".{ext}"
        candidates = [c for c in candidates if c["ext"] == want]
        if not candidates:
            return {"root": base.as_posix(), "candidates": [], "forged": [],
                    "error": f"no uncovered files with extension {want}"}
    ask_model = generate or backend_generate(base, model)
    report: dict[str, Any] = {"root": base.as_posix(), "candidates": candidates,
                              "forged": [_forged(base, c, ask_model, attempts,
                                                 dry_run) for c in candidates]}
    if not dry_run and any(entry["ok"] for entry in report["forged"]):
        from ..indexing.indexer import index_repo
        report["index"] = index_repo(base, embedder=embedder)
    report["seconds"] = round(time.time() - started, 2)
    return report


def _forged(base: Path, candidate: Candidate, generate: Generate,
            attempts: int, dry_run: bool) -> dict[str, Any]:
    """Generate-validate-repair for ONE extension, ≤ `attempts` rounds."""
    from ._prompt import generation_prompt

    samples = [(rel, (base / rel).read_text(encoding="utf-8", errors="replace"))
               for rel in candidate["samples"]]
    feedback = ""
    entry: dict[str, Any] = {"ext": candidate["ext"], "files": candidate["files"],
                             "attempts": 0, "ok": False}
    for round_number in range(1, attempts + 1):
        entry["attempts"] = round_number
        raw = generate(generation_prompt(candidate["ext"], base.name,
                                         samples, feedback))
        code = extract_code(raw)
        ok, message, stats = validate_strategy(base, code, candidate["ext"],
                                               candidate["paths"])
        entry["validation"] = message
        if ok:
            entry.update(ok=True, stats=stats)
            if dry_run:
                entry["code"] = code
            else:
                entry["installed"] = install(base, candidate["ext"], code).as_posix()
            break
        feedback = message
    return entry


def install(root: Path | str, ext: str, code: str) -> Path:
    """Write the VETTED module to the repo and record its sha in the trust
    store — from here on every index_repo loads it without forge."""
    target = Path(root).resolve() / STRATEGY_DIR / f"{ext.lstrip('.')}.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    trust_file(target)
    return target
