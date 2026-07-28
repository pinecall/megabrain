"""forge: the census, the partition oracle as install gate, the repair loop,
and index survival. All offline — the model is an injected fake."""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.forge import detect, forge, validate_strategy
from megabrain.indexing.indexer import index_repo
from megabrain.indexing.trust import load_repo_strategies
from megabrain.storage import Store
from tests.unit.forge.fixtures import BAD, GOOD, SQL
from tests.unit.indexing.fake import CountingEmbedder


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "a.sql").write_text(SQL, encoding="utf-8")
    (tmp_path / "b.sql").write_text(SQL.replace("users", "invoices"), encoding="utf-8")
    (tmp_path / "c.sql").write_text("CREATE TABLE tiny (id INTEGER);\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\0\0\0")
    (tmp_path / "one.xyz").write_text("lonely\n", encoding="utf-8")
    return tmp_path


def test_detect_census(repo: Path) -> None:
    exts = {c["ext"] for c in detect(repo)}
    assert ".sql" in exts                     # 3 files, uncovered
    assert ".py" not in exts                  # covered by the built-in registry
    assert ".png" not in exts                 # binary sniff
    assert ".xyz" not in exts                 # below MIN_FILES
    sql = next(c for c in detect(repo) if c["ext"] == ".sql")
    assert sql["files"] == 3 and len(sql["samples"]) >= 1


def test_oracle_rejects_a_bad_partition(repo: Path) -> None:
    ok, msg, _ = validate_strategy(repo, BAD, ".sql", ["a.sql", "b.sql"])
    assert not ok and "partition" in msg


def test_repair_loop_installs_only_vetted_code(repo: Path) -> None:
    prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        prompts.append(prompt)
        if len(prompts) == 1:
            return f"```python\n{BAD}```"
        assert "PREVIOUS ATTEMPT FAILED" in prompt      # feedback flows back
        return f"```python\n{GOOD}```"

    report = forge(repo, ext=".sql", generate=fake_model,
                   embedder=CountingEmbedder())
    entry = report["forged"][0]
    assert entry["ok"] and entry["attempts"] == 2
    installed = repo / ".megabrain/strategies/sql.py"
    assert installed.exists() and "SqlStrategy" in installed.read_text(encoding="utf-8")
    assert [s for s in load_repo_strategies(repo) if ".sql" in s.exts]
    with Store(repo) as store:
        assert "a.sql" in store.files.all_paths()       # the reindex ingested them


def test_forge_gives_up_after_attempts(repo: Path) -> None:
    report = forge(repo, ext=".sql", attempts=2,
                   generate=lambda _prompt: f"```python\n{BAD}```")
    entry = report["forged"][0]
    assert not entry["ok"] and entry["attempts"] == 2
    assert not (repo / ".megabrain/strategies/sql.py").exists()


def test_dry_run_returns_code_without_installing(repo: Path) -> None:
    report = forge(repo, ext=".sql", dry_run=True,
                   generate=lambda _prompt: f"```python\n{GOOD}```")
    entry = report["forged"][0]
    assert entry["ok"] and "SqlStrategy" in entry["code"]
    assert not (repo / ".megabrain/strategies").exists()
    assert "index" not in report


def test_a_reindex_keeps_the_forged_extension(repo: Path) -> None:
    """The whole point of the trust-gated install: index_repo — including any
    later refresh — loads the strategy without forge in the loop."""
    forge(repo, ext=".sql", generate=lambda _p: f"```python\n{GOOD}```",
          embedder=CountingEmbedder())
    index_repo(repo, embedder=CountingEmbedder())       # a plain re-index
    with Store(repo) as store:
        assert "a.sql" in store.files.all_paths()
