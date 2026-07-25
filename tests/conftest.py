"""Fixtures shared by the whole suite.

The suite is fully OFFLINE: no credential, no socket, no real sleeping. A test
that would need any of those is testing the network, not this engine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

from megabrain._home import HOME_VAR


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every MEGABRAIN_* setting comes OUT of the environment, for every test.

    The developer's own shell configures the engine — a model here, a provider
    there — and those leaked in: a test asserting the built-in default failed
    on the machine that had an override set, and passed everywhere else. A
    suite whose result depends on whose shell ran it is not a suite.

    The golden corpus variables are kept: they point the retrieval gate at a
    real index, and stripping them would silently turn a measurement into a
    skip.
    """
    for name in list(os.environ):
        if name.startswith("MEGABRAIN_") and not name.startswith("MEGABRAIN_GOLDEN"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory: pytest.TempPathFactory,
                  monkeypatch: pytest.MonkeyPatch) -> Path:
    """Machine-global state goes to a temp directory, for EVERY test.

    The embedding cache and the repo registry both live under one home. Left
    alone, running this suite would write real entries into the developer's
    own `~/.megabrain` — junk repositories in their registry, cache files from
    fixtures. Autouse, because the danger is in the test that forgets.
    """
    home = tmp_path_factory.mktemp("megabrain-home")
    monkeypatch.setenv(HOME_VAR, str(home))
    return home


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Backoff is real time; a test suite should not pay it.

    Patched at the module the policy actually calls, so a delay that is
    computed but never awaited still shows up as a missing call rather than
    silently passing.
    """
    import time

    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    yield
