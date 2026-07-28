"""Repo-local strategies, gated by a trust store the repository cannot touch.

`<repo>/.megabrain/strategies/*.py` runs only when its sha256 is recorded in
`~/.megabrain/trust.json` — the USER\'s home, written only by this machine\'s
own forge/install — and any edit after approval changes the sha and silently
revokes it. A cloned repo that ships strategies gets NOTHING run until someone
here vets it. Loading fails soft (indexing must not die on a side file);
installing fails loud.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, cast

from .._home import megabrain_home
from .strategies import Strategy

__all__ = ["STRATEGY_DIR", "trust_store", "trust_file", "is_trusted",
           "instantiate_strategies", "load_repo_strategies"]

STRATEGY_DIR = ".megabrain/strategies"

log = logging.getLogger(__name__)


def trust_store() -> Path:
    return megabrain_home() / "trust.json"


def trust_file(path: Path) -> None:
    """Record the file's current sha256 as approved, keeping other entries."""
    store = trust_store()
    entries = _entries(store)
    entries[path.resolve().as_posix()] = _sha(path)
    store.parent.mkdir(parents=True, exist_ok=True)
    temp = store.with_suffix(".json.tmp")
    temp.write_text(json.dumps(entries, indent=1, sort_keys=True), encoding="utf-8")
    temp.replace(store)


def is_trusted(path: Path) -> bool:
    """Approved, AND byte-identical to what was approved."""
    recorded = _entries(trust_store()).get(path.resolve().as_posix())
    return recorded is not None and recorded == _sha(path)


def instantiate_strategies(code: str, *, origin: str) -> list[Strategy]:
    """Every strategy-shaped class the module defines, instantiated.

    `exec` of vetted source is forge's accepted risk; nothing reaches here
    without the sha gate or forge's oracle. Raises on a broken module — the
    CALLERS decide whether that is fatal (forge) or a skip (index time)."""
    namespace: dict[str, Any] = {"__name__": f"megabrain_strategy_{origin}"}
    exec(compile(code, origin, "exec"), namespace)  # noqa: S102
    return [obj() for obj in namespace.values()
            if isinstance(obj, type) and _strategy_shaped(obj)]


def load_repo_strategies(root: Path) -> list[Strategy]:
    """Every TRUSTED strategy installed under this repository, or nothing.

    Untrusted files are skipped with a log line, never an error — refusing to
    index over a file that arrived with a clone would be a shippable DoS."""
    found: list[Strategy] = []
    for path in sorted((Path(root) / STRATEGY_DIR).glob("*.py")):
        if not is_trusted(path):
            log.warning("skipping untrusted strategy %s", path)
            continue
        try:
            found.extend(instantiate_strategies(
                path.read_text(encoding="utf-8"), origin=path.name))
        except Exception:                               # noqa: BLE001 — fail soft
            log.warning("trusted strategy %s failed to load", path, exc_info=True)
    return found


def _strategy_shaped(cls: type) -> bool:
    return bool(getattr(cls, "exts", None)) and callable(getattr(cls, "parse", None))


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _entries(store: Path) -> dict[str, str]:
    try:
        loaded: object = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    entries = cast("dict[object, object]", loaded)
    return {str(key): str(value) for key, value in entries.items()}
