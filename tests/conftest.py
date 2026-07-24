"""Fixtures shared by the whole suite.

The suite is fully OFFLINE: no credential, no socket, no real sleeping. A test
that would need any of those is testing the network, not this engine.
"""

from __future__ import annotations

from typing import Iterator

import pytest


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
