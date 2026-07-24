"""Fixtures shared by the whole suite.

The suite is fully OFFLINE: no credential, no socket, no real sleeping. A test
that would need any of those is testing the network, not this engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from megabrain._home import HOME_VAR


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
