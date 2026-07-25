"""`megabrain.json` — a repository's own configuration.

One file per project, checked in, holding what used to be spread across two
dotfiles and four environment variables. The point is that it TRAVELS: an env
var lives in one shell and is invisible to the next person who clones the repo,
so a project's choice of models and exclusions was never really the project's.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megabrain.project import CONFIG_FILE, load_project


def write_config(root: Path, payload: object) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / CONFIG_FILE).write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_a_repo_with_no_config_gets_the_measured_defaults(tmp_path: Path) -> None:
    project = load_project(tmp_path)
    assert project.narrator_model == "google/gemini-3.1-flash-lite"
    assert project.rerank_model == "google/gemini-3.5-flash-lite"
    assert project.ignore == () and project.queries == ()


def test_the_project_names_its_own_models(tmp_path: Path) -> None:
    write_config(tmp_path, {"models": {"narrator": "anthropic/claude-haiku-4.5",
                                       "rerank": "google/gemini-3.1-flash-lite"}})
    project = load_project(tmp_path)
    assert project.narrator_model == "anthropic/claude-haiku-4.5"
    assert project.rerank_model == "google/gemini-3.1-flash-lite"


def test_naming_one_model_leaves_the_other_at_its_default(tmp_path: Path) -> None:
    """They are separate jobs. A repo that only cares which model narrates must
    not silently inherit that choice for the judge, which wants an obedient
    fast model and measurably suffers from a big one."""
    write_config(tmp_path, {"models": {"narrator": "some/model"}})
    assert load_project(tmp_path).rerank_model == "google/gemini-3.5-flash-lite"


def test_the_project_config_BEATS_the_environment(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Deliberate precedence, and the reason for this file: the config is
    checked in and shared, the env var is one person's shell."""
    monkeypatch.setenv("MEGABRAIN_RERANK_MODEL", "from/the-shell")
    write_config(tmp_path, {"models": {"rerank": "from/the-repo"}})
    assert load_project(tmp_path).rerank_model == "from/the-repo"


def test_the_environment_still_works_when_the_repo_is_silent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGABRAIN_RERANK_MODEL", "from/the-shell")
    assert load_project(tmp_path).rerank_model == "from/the-shell"


def test_ignore_patterns_come_from_the_config(tmp_path: Path) -> None:
    write_config(tmp_path, {"ignore": ["dist", "vendor/**"]})
    assert load_project(tmp_path).ignore == ("dist", "vendor/**")


def test_the_LEGACY_dotfiles_are_still_read(tmp_path: Path) -> None:
    """Repositories in the wild have `.megabrainignore` and
    `.megabrainqueries`. Dropping them would silently start indexing
    directories somebody deliberately excluded."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".megabrainignore").write_text("build\n# a comment\nfixtures\n",
                                               encoding="utf-8")
    (tmp_path / ".megabrainqueries").write_text("how does auth work\n\nwhere is retry\n",
                                                encoding="utf-8")
    project = load_project(tmp_path)
    assert project.ignore == ("build", "fixtures")
    assert project.queries == ("how does auth work", "where is retry")


def test_both_sources_merge_rather_than_one_winning(tmp_path: Path) -> None:
    """A repo mid-migration has both. Preferring one would quietly drop half
    the exclusions, and the symptom is a slightly bigger index nobody notices."""
    write_config(tmp_path, {"ignore": ["dist"]})
    (tmp_path / ".megabrainignore").write_text("build\n", encoding="utf-8")
    assert set(load_project(tmp_path).ignore) == {"dist", "build"}


def test_the_repo_authors_its_own_starter_questions(tmp_path: Path) -> None:
    write_config(tmp_path, {"queries": ["how does the scoring fuse?",
                                        "where are edges written?"]})
    assert load_project(tmp_path).queries == ("how does the scoring fuse?",
                                              "where are edges written?")


def test_a_malformed_config_does_not_stop_the_engine(tmp_path: Path) -> None:
    """It is configuration, not a dependency. A broken JSON file must not make
    a repository unindexable — it must fall back and stay usable."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / CONFIG_FILE).write_text("{not json", encoding="utf-8")
    project = load_project(tmp_path)
    assert project.narrator_model == "google/gemini-3.1-flash-lite"
    assert project.malformed is True, "and it says so, rather than pretending"


def test_a_config_of_the_wrong_shape_is_ignored_field_by_field(tmp_path: Path) -> None:
    """Half a valid config is common while somebody is editing it. Each field
    is taken only if it has the right shape."""
    write_config(tmp_path, {"ignore": "dist", "models": ["nope"], "queries": 3})
    project = load_project(tmp_path)
    assert project.ignore == () and project.queries == ()
    assert project.narrator_model == "google/gemini-3.1-flash-lite"
