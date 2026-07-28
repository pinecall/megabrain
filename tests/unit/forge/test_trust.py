"""The trust store: repo-local strategies run only after THIS user vetted them.

The sha gate is the whole security story of forge — a cloned repository must
not be able to make the indexer execute code just by shipping a file in
`.megabrain/strategies/`.
"""

from __future__ import annotations

import json
from pathlib import Path

from megabrain.indexing.trust import (
    STRATEGY_DIR,
    instantiate_strategies,
    load_repo_strategies,
    trust_file,
    trust_store,
)
from tests.unit.forge.fixtures import GOOD


def _installed(root: Path) -> Path:
    target = root / STRATEGY_DIR / "sql.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(GOOD, encoding="utf-8")
    return target


def test_instantiate_finds_the_claiming_class() -> None:
    strategies = instantiate_strategies(GOOD, origin="<test>")
    assert [s for s in strategies if ".sql" in s.exts]


def test_untrusted_module_is_skipped_until_approved(tmp_path: Path) -> None:
    target = _installed(tmp_path)
    assert load_repo_strategies(tmp_path) == []           # no trust entry yet
    trust_file(target)
    assert [s for s in load_repo_strategies(tmp_path) if ".sql" in s.exts]


def test_an_edit_after_approval_revokes_the_trust(tmp_path: Path) -> None:
    target = _installed(tmp_path)
    trust_file(target)
    target.write_text(GOOD + "\n# edited after approval\n", encoding="utf-8")
    assert load_repo_strategies(tmp_path) == []


def test_the_store_is_json_outside_the_repo(tmp_path: Path) -> None:
    """The trust record lives in the USER's home, never in the repo — a repo
    that could write its own trust entries would be its own gatekeeper."""
    target = _installed(tmp_path)
    trust_file(target)
    store = trust_store()
    assert tmp_path not in store.parents and store != tmp_path
    assert target.resolve().as_posix() in json.loads(store.read_text(encoding="utf-8"))


def test_a_broken_module_loads_as_nothing(tmp_path: Path) -> None:
    """A syntax error in a trusted file must not take indexing down."""
    target = _installed(tmp_path)
    target.write_text("def (broken\n", encoding="utf-8")
    trust_file(target)
    assert load_repo_strategies(tmp_path) == []
