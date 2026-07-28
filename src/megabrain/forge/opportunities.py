"""Where the built-in chunks a covered file poorly. Deterministic, no model.

Liberal by design — the ab_gate is the real arbiter, so detection only has to
surface plausible cases: a dominant data-table literal (the proven, high-yield
shape), a blob (most of the file in one chunk), or a line-window fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ..indexing._exclude import Excluder, load_ignore
from ..indexing.builtin import default_registry
from ..indexing.discover import MAX_FILE_BYTES
from .diagnose import SHAPE_RANK, diagnose

__all__ = ["detect_specialization", "MAX_OPP_FILES"]

MAX_OPP_FILES = 40


def detect_specialization(root: Path | str,
                          exclude: Sequence[str] = ()) -> list[dict[str, Any]]:
    """Covered files the built-in chunks poorly, grouped by extension."""
    base = Path(root).resolve()
    registry = default_registry()
    excluder = Excluder.build([*load_ignore(base), *exclude])
    by_ext: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(base.rglob("*")):
        relpath = path.relative_to(base).as_posix()
        if (not path.is_file() or excluder.excludes(relpath)
                or "/test" in f"/{relpath}" or "/spec" in f"/{relpath}"):
            continue
        strategy = registry.for_path(relpath)
        if strategy is None or path.stat().st_size > MAX_FILE_BYTES:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if diagnosis := diagnose(relpath, source, strategy):
            shape, reason = diagnosis
            by_ext.setdefault(path.suffix, []).append(
                {"rel": relpath, "shape": shape, "reason": reason,
                 "lines": len(source.splitlines())})
    return [_opportunity(ext, files)
            for ext, files in sorted(by_ext.items(), key=lambda kv: -len(kv[1]))]


def _opportunity(ext: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    files.sort(key=lambda f: -int(f["lines"]))
    strongest = sorted(files, key=lambda f: (-SHAPE_RANK[str(f["shape"])],
                                             -int(f["lines"])))
    return {"ext": ext, "files": [f["rel"] for f in files[:MAX_OPP_FILES]],
            "count": len(files), "target": strongest[0]["rel"],
            "diagnoses": {f["rel"]: f["reason"] for f in strongest[:6]},
            "samples": [f["rel"] for f in strongest[:3]]}
