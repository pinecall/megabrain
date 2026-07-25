"""Serving the studio's files.

A static file server is the one place in this codebase where a path comes from
a stranger and is turned into a filesystem read. Every test here is about that
sentence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.transports.http.messages import Request
from megabrain.transports.http.routes.static import UI_DIR, static_route


@pytest.fixture
def ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "index.html").write_text("<h1>studio</h1>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("not yours", encoding="utf-8")
    monkeypatch.setattr("megabrain.transports.http.routes.static.UI_DIR", tmp_path)
    return tmp_path


def _get(path: str) -> Request:
    return Request(method="GET", path=path)


@pytest.mark.usefixtures("ui")
def test_the_root_serves_the_studio() -> None:
    reply = static_route(_get("/"))
    assert reply.status == 200
    assert reply.body == b"<h1>studio</h1>"
    assert reply.content_type == "text/html; charset=utf-8"


@pytest.mark.usefixtures("ui")
def test_an_asset_is_served_with_its_own_type() -> None:
    reply = static_route(_get("/ui/app.js"))
    assert reply.body == b"console.log(1)"
    assert "javascript" in reply.content_type


@pytest.mark.usefixtures("ui")
def test_a_nested_asset_is_served() -> None:
    assert static_route(_get("/ui/icons/logo.svg")).status == 200


@pytest.mark.parametrize("attack", [
    "/ui/../secret.txt",
    "/ui/../../etc/passwd",
    "/ui/icons/../../secret.txt",
    "/ui/%2e%2e/secret.txt",
    "/ui//etc/passwd",
])
@pytest.mark.usefixtures("ui")
def test_no_path_escapes_the_ui_directory(attack: str) -> None:
    """The whole reason this module is separate.

    A served path is attacker-controlled text becoming a filesystem read, and
    every one of these spellings has been someone's CVE. The check is on the
    RESOLVED path, not on the text — filtering ".." by string is how the
    encoded and doubled forms get through.
    """
    reply = static_route(_get(attack))
    assert reply.status in (400, 404), f"{attack} was served"
    assert b"not yours" not in (reply.body or b"")


@pytest.mark.usefixtures("ui")
def test_a_missing_file_is_404() -> None:
    assert static_route(_get("/ui/nope.js")).status == 404


def test_an_absent_bundle_says_how_to_build_it(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """A studio nobody built must not answer with a bare 404: the reader is a
    developer who cloned the repo, and the fix is one command."""
    monkeypatch.setattr("megabrain.transports.http.routes.static.UI_DIR",
                        tmp_path / "never-built")
    reply = static_route(_get("/"))
    assert reply.status == 503
    assert b"studio" in (reply.body or b"")


def test_the_shipped_ui_directory_is_inside_the_package() -> None:
    """Anti-vacuum: if UI_DIR ever pointed outside the installed package, the
    studio would work from a checkout and 404 from a wheel."""
    assert UI_DIR.name == "ui"
    assert "megabrain" in str(UI_DIR)


def test_the_BUILT_studio_is_present_and_served() -> None:
    """The bundle is committed, so a clone without node still serves the UI.

    This is the assertion that fails when someone edits studio/src and forgets
    to rebuild — together with the CI job that rebuilds and diffs, the two make
    a stale bundle impossible to ship quietly.
    """
    assert (UI_DIR / "index.html").is_file(), "run: cd studio && npm run build"
    assert (UI_DIR / "app.js").is_file()
    reply = static_route(_get("/"))
    assert reply.status == 200
    assert b"megabrain" in (reply.body or b"")
    assert b'src="ui/app.js"' in (reply.body or b"")
