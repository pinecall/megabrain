"""`megabrain install` — the MCP registration table.

Every test runs against a FAKE $HOME, so the suite can never touch the
developer's real assistant configs. The invariant under all of them: megabrain
owns exactly one key, and every other server the user configured survives.

Ported from v2's test_install.py, which is the specification — the file formats
and the merge semantics are unchanged, only the module the entry points at.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megabrain.transports import install
from megabrain.transports.cli.main import main
from megabrain.transports.install.platforms import PLATFORMS, entry


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    return tmp_path


def _rows(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["platform"]): row for row in rows}


# ── what is on this machine ──────────────────────────────────────────────

@pytest.mark.usefixtures("home")
def test_detect_reports_not_installed_on_an_empty_home() -> None:
    rows = _rows(list(install.detect()))
    assert set(rows) == set(PLATFORMS)
    assert not any(row["installed"] for row in rows.values())
    assert not any(row["registered"] for row in rows.values())


def test_gemini_is_not_claimed_when_only_antigravity_exists(home: Path) -> None:
    """~/.gemini exists for Antigravity too, which nests under it. Keying off
    the settings FILE is what stops Gemini CLI being claimed for a directory
    another product made."""
    (home / ".gemini" / "antigravity").mkdir(parents=True)
    rows = _rows(list(install.detect()))
    assert rows["antigravity"]["installed"] is True
    assert rows["gemini"]["installed"] is False


def test_detect_sees_an_existing_registration(home: Path) -> None:
    (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"megabrain": entry()}}), encoding="utf-8")
    assert _rows(list(install.detect()))["claude"]["registered"] is True


# ── the entry itself ─────────────────────────────────────────────────────

def test_the_entry_points_at_this_interpreter_and_the_v3_server() -> None:
    """The module MOVED in v3. An entry naming the v2 path installs cleanly and
    fails at launch, inside the host, where nobody sees the traceback."""
    import sys

    assert entry()["command"] == sys.executable
    assert entry()["args"] == ["-m", "megabrain.transports.mcp"]


# ── JSON hosts ───────────────────────────────────────────────────────────

def test_json_install_preserves_other_servers(home: Path) -> None:
    config = home / ".claude.json"
    config.write_text(json.dumps({
        "mcpServers": {"mypry": {"command": "node", "args": ["x.js"]}},
        "projects": {"/some/repo": {"keep": True}},
    }), encoding="utf-8")
    install.apply(platform="claude")
    written = json.loads(config.read_text(encoding="utf-8"))
    assert "megabrain" in written["mcpServers"]
    assert written["mcpServers"]["mypry"] == {"command": "node", "args": ["x.js"]}, \
        "must not clobber other MCP servers"
    assert written["projects"] == {"/some/repo": {"keep": True}}, \
        "must not touch unrelated top-level config"


def test_install_repairs_a_stale_entry_and_is_idempotent(home: Path) -> None:
    """The entry is REPLACED, not merged into: a PYTHONPATH left over from an
    old checkout is exactly what re-running this is supposed to cure."""
    config = home / ".claude.json"
    config.write_text(json.dumps({"mcpServers": {"megabrain": {
        "command": "python3", "env": {"PYTHONPATH": "/old/checkout"}}}}),
        encoding="utf-8")
    install.apply(platform="claude")
    written = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["megabrain"]
    assert "env" not in written
    assert written["args"] == ["-m", "megabrain.transports.mcp"]
    once = config.read_text(encoding="utf-8")
    install.apply(platform="claude")
    assert config.read_text(encoding="utf-8") == once, "re-running must be a no-op"


def test_remove_drops_only_megabrain(home: Path) -> None:
    config = home / ".claude.json"
    config.write_text(json.dumps({"mcpServers": {"mypry": {"command": "node"}}}),
                      encoding="utf-8")
    install.apply(platform="claude")
    install.apply(platform="claude", remove=True)
    written = json.loads(config.read_text(encoding="utf-8"))
    assert "megabrain" not in written["mcpServers"]
    assert "mypry" in written["mcpServers"]


def test_broken_json_is_reported_not_overwritten(home: Path) -> None:
    """Someone's hand-edited config with a trailing comma is not a reason to
    replace their file with ours."""
    config = home / ".claude.json"
    config.write_text('{"mcpServers": {,}}', encoding="utf-8")
    action = str(_rows(list(install.apply(platform="claude")))["claude"]["action"])
    assert action.startswith("FAILED")
    assert config.read_text(encoding="utf-8") == '{"mcpServers": {,}}'


# ── the TOML host ────────────────────────────────────────────────────────

def test_toml_install_appends_and_replaces_only_our_section(home: Path) -> None:
    """No TOML writer in the stdlib and megabrain takes no dependencies, so the
    section is replaced by hand — which has to leave comments alone."""
    config = home / ".codex" / "config.toml"
    config.parent.mkdir()
    config.write_text('# my notes\n[mcp_servers.other]\ncommand = "node"\n',
                      encoding="utf-8")
    install.apply(platform="codex")
    text = config.read_text(encoding="utf-8")
    assert "# my notes" in text, "comments must survive"
    assert "[mcp_servers.other]" in text, "other servers must survive"
    assert "[mcp_servers.megabrain]" in text
    install.apply(platform="codex")
    assert config.read_text(encoding="utf-8").count("[mcp_servers.megabrain]") == 1


def test_toml_remove(home: Path) -> None:
    config = home / ".codex" / "config.toml"
    config.parent.mkdir()
    config.write_text('[mcp_servers.other]\ncommand = "node"\n', encoding="utf-8")
    install.apply(platform="codex")
    install.apply(platform="codex", remove=True)
    text = config.read_text(encoding="utf-8")
    assert "[mcp_servers.megabrain]" not in text
    assert "[mcp_servers.other]" in text


# ── choosing what to write ───────────────────────────────────────────────

def test_auto_install_skips_platforms_that_are_absent(home: Path) -> None:
    (home / ".codex").mkdir()
    actions = {str(r["platform"]): str(r["action"]) for r in install.apply()}
    assert actions["codex"] == "registered"
    assert "skipped" in actions["cursor"]


def test_an_explicit_platform_is_written_even_if_undetected(home: Path) -> None:
    """Asking for one by name is a decision, not a guess: the config file may
    simply not exist yet on a fresh install."""
    install.apply(platform="cursor")
    assert (home / ".cursor" / "mcp.json").is_file()


@pytest.mark.usefixtures("home")
def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown platform"):
        install.apply(platform="nope")


# ── what the person reads ────────────────────────────────────────────────

def test_the_report_counts_what_it_did_and_names_the_three_tools(home: Path) -> None:
    (home / ".codex").mkdir()
    text = install.render(install.apply())
    assert "Registered megabrain in 1 platform(s)" in text
    assert "megabrain_ask" in text and "megabrain_search" in text
    assert "Restart your assistant" in text


@pytest.mark.usefixtures("home")
def test_the_report_says_so_when_nothing_was_touched() -> None:
    assert "No platforms touched" in install.render(install.apply())


def test_removal_reads_as_removal(home: Path) -> None:
    (home / ".codex").mkdir()
    install.apply()
    text = install.render(install.apply(remove=True), remove=True)
    assert "Unregistered megabrain in 1 platform(s)" in text
    assert "Restart your assistant" not in text, "nothing to pick up after a removal"


# ── the CLI ──────────────────────────────────────────────────────────────

def test_cli_list_changes_nothing(home: Path,
                                  capsys: pytest.CaptureFixture[str]) -> None:
    (home / ".codex").mkdir()
    assert main(["install", "--list"]) == 0
    out = capsys.readouterr().out
    assert "Codex" in out and "not registered" in out
    assert not (home / ".codex" / "config.toml").exists(), "--list wrote a file"


def test_cli_installs_and_removes(home: Path,
                                  capsys: pytest.CaptureFixture[str]) -> None:
    (home / ".cursor").mkdir()
    assert main(["install"]) == 0
    assert "Registered" in capsys.readouterr().out
    written = json.loads((home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert written["mcpServers"]["megabrain"]["args"] == ["-m", "megabrain.transports.mcp"]
    assert main(["install", "--remove"]) == 0
    assert "Unregistered" in capsys.readouterr().out


@pytest.mark.usefixtures("home")
def test_cli_rejects_an_unknown_platform_without_a_traceback() -> None:
    """argparse's own exit code: a script can tell "you typed it wrong" from
    "the engine failed"."""
    with pytest.raises(SystemExit) as caught:
        main(["install", "--platform", "nope"])
    assert caught.value.code == 2
