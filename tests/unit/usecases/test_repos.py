"""The registry: a file this engine SHARES with another one.

`~/.megabrain/registry.json` is not ours alone. The engine this one replaces
reads and writes the same path, in its own shape, and both may be installed at
once — so every test here is about coexisting rather than about correctness in
isolation. Getting it wrong destroys somebody's list of repositories, which is
data no re-index brings back.
"""

from __future__ import annotations

import json
from pathlib import Path

from megabrain.storage import Store
from megabrain.usecases.repos import known, registry_path, remember


def write_registry(payload: object) -> None:
    registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry_path().write_text(json.dumps(payload), encoding="utf-8")


def indexed(root: Path) -> Path:
    """A directory with a real index in it, so `known()` keeps it."""

    root.mkdir(parents=True, exist_ok=True)
    with Store(root) as store:
        store.files.upsert("a.py", "sha", "", None)
    return root


# ---- reading somebody else's shape -----------------------------------------


def test_the_OTHER_engines_format_is_read_not_ignored(tmp_path: Path) -> None:
    """It writes a dict keyed by path, with metadata per entry. Read as a list
    it looked like nothing was registered, and the studio said so."""
    repo = indexed(tmp_path / "alpha")
    write_registry({str(repo): {"path": str(repo), "name": "alpha",
                                "files": 3, "chunks": 9}})
    assert [entry["path"] for entry in known()] == [str(repo)]


def test_our_own_list_shape_still_reads(tmp_path: Path) -> None:
    """Written by an earlier version of this module. Tolerated so an upgrade
    does not look like an empty machine."""
    repo = indexed(tmp_path / "beta")
    write_registry([str(repo)])
    assert [entry["path"] for entry in known()] == [str(repo)]


def test_a_corrupt_registry_is_not_fatal() -> None:
    registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry_path().write_text("{not json", encoding="utf-8")
    assert known() == []


# ---- writing without destroying ---------------------------------------------


def test_remembering_one_repo_KEEPS_the_others(tmp_path: Path) -> None:
    """The bug this file exists for: writing our shape replaced the whole
    file, and every repository the other engine had registered was gone."""
    theirs = indexed(tmp_path / "theirs")
    ours = indexed(tmp_path / "ours")
    write_registry({str(theirs): {"path": str(theirs), "name": "theirs",
                                  "files": 7, "chunks": 20}})

    remember(ours)

    assert {entry["path"] for entry in known()} == {str(theirs), str(ours)}


def test_the_other_engines_metadata_survives_our_write(tmp_path: Path) -> None:
    """Fields we do not use are still theirs. Dropping them on write is a
    quieter kind of destruction than dropping the entry."""
    theirs = indexed(tmp_path / "theirs")
    write_registry({str(theirs): {"path": str(theirs), "name": "theirs",
                                  "embed_model": "some-model",
                                  "last_index": 1784964655.9}})
    remember(indexed(tmp_path / "ours"))

    stored = json.loads(registry_path().read_text(encoding="utf-8"))
    assert stored[str(theirs)]["embed_model"] == "some-model"
    assert stored[str(theirs)]["last_index"] == 1784964655.9


def test_we_write_the_shape_the_other_engine_can_read(tmp_path: Path) -> None:
    """A dict keyed by path, with `path` and `name` inside — otherwise the
    other engine reads OUR writes as nothing, and the destruction is mutual."""
    repo = indexed(tmp_path / "gamma")
    remember(repo)
    stored = json.loads(registry_path().read_text(encoding="utf-8"))
    assert isinstance(stored, dict)
    assert stored[str(repo)]["path"] == str(repo)
    assert stored[str(repo)]["name"] == "gamma"


def test_remembering_twice_does_not_duplicate(tmp_path: Path) -> None:
    repo = indexed(tmp_path / "delta")
    remember(repo)
    remember(repo)
    assert len(json.loads(registry_path().read_text(encoding="utf-8"))) == 1


def test_a_repo_whose_index_is_gone_is_hidden_but_NOT_deleted(tmp_path: Path) -> None:
    """Hidden, because a rail entry that fails when clicked is worse than a
    shorter list. Not deleted, because the other engine may know something
    about that path that we do not — a shared file is nobody's to garbage
    collect."""
    missing = tmp_path / "vanished"
    write_registry({str(missing): {"path": str(missing), "name": "vanished"}})
    assert known() == []
    assert str(missing) in json.loads(registry_path().read_text(encoding="utf-8"))
