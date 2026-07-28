"""The CLI, driven the way a person drives it: argv in, text and a code out.

Not by calling the command functions directly — the parsing, the dispatch and
the exit code ARE the surface, and they are what breaks when a flag is added.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megabrain.transports.cli.main import main
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No network in a CLI test.

    Patched where each caller LOOKS the class up, which is the seam the CLI
    actually goes through — the commands take no embedder argument on purpose,
    since a production surface that lets its caller inject one has an
    injection point nobody wants.

    TWO seams, because there are two: `load_state` for the query side, and
    `indexer._default_embedder` for `index`. Only the first was patched, so
    `test_index_reports_what_it_did` reached for a real credential and passed
    only on a machine that had one — green here, red on every CI runner, for as
    long as the CI was red for other reasons and nobody read it.
    """
    monkeypatch.setattr("megabrain.search.state.Embedder", CountingEmbedder)
    monkeypatch.setattr("megabrain.providers.embeddings.Embedder", CountingEmbedder)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {"svc.py": "import util\n\n\nclass Service:\n"
                               "    def handle(self, request):\n"
                               '        """Answer one request."""\n'
                               "        return util.run(request)\n",
                     "util.py": "def run(request):\n    return request\n"})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def test_search_prints_a_code_map(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["search", "how does Service handle a request", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "# megabrain" in out
    assert "## CORE" in out
    assert "svc.py" in out


def test_search_json_emits_the_contract(repo: Path,
                                        capsys: pytest.CaptureFixture[str]) -> None:
    """A caller piping this writes against contracts/, not against a rendering
    — so the JSON must BE the bundle, not a flattened view of it."""
    assert main(["search", "handle", str(repo), "--json"]) == 0
    bundle = json.loads(capsys.readouterr().out)
    assert {"query", "repo", "tier1", "tier2", "anchors", "ms"} <= set(bundle)


def test_index_reports_what_it_did(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["index", str(repo), "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "2 files" in out and "edges" in out


def test_get_shows_one_symbol(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["get", "svc.py", str(repo), "--symbol", "handle"]) == 0
    out = capsys.readouterr().out
    assert "def handle" in out
    assert "class Service" not in out, "--symbol returned the whole file"


def test_get_outline_lists_declarations_without_code(
        repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["get", "svc.py", str(repo), "--outline"]) == 0
    out = capsys.readouterr().out
    assert "Service" in out and "```" not in out


def test_get_warns_when_the_file_changed_since_indexing(
        repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The lines a bundle pointed at were the indexed ones. Serving newer text
    silently would answer about code the ranking never saw."""
    (repo / "util.py").write_text("def run(request):\n    return 42\n", encoding="utf-8")
    assert main(["get", "util.py", str(repo)]) == 0
    assert "changed since it was indexed" in capsys.readouterr().out


def test_an_engine_error_is_one_line_and_exit_1(tmp_path: Path,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    """A traceback is for whoever can fix the code; this person is trying to
    use the tool, so they get the command that fixes it."""
    assert main(["search", "anything", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "megabrain index" in err
    assert "Traceback" not in err


def test_bad_usage_exits_2_not_1() -> None:
    """argparse's own code, kept distinct: a script can tell "you typed it
    wrong" from "the engine failed"."""
    with pytest.raises(SystemExit) as caught:
        main(["search"])
    assert caught.value.code == 2


def test_every_command_is_reachable() -> None:
    """Anti-vacuum: a command module that stops registering itself would leave
    the rest of this file passing."""
    from megabrain.transports.cli.main import build_parser

    actions = [a for a in build_parser()._actions if a.dest == "command"]
    assert set(actions[0].choices) == {"index", "scan", "search", "ask", "grep",
                                      "get", "graph", "ui", "studio", "cache",
                                      "forge", "install"}  # type: ignore[union-attr]


def test_studio_is_still_accepted_as_an_alias_of_ui() -> None:
    """`megabrain studio` is in a published README and in the demo box's deploy
    script. The verb is `ui` now; the old spelling keeps working."""
    from megabrain.transports.cli.main import build_parser

    for verb in ("ui", "studio"):
        args = build_parser().parse_args([verb, "--port", "0"])
        assert args.port == 0
        assert args.run.__module__.endswith("commands.ui")

def test_ui_exposes_trust_proxy() -> None:
    """The public demo runs behind nginx, where every socket is the proxy's —
    v2 had the flag and the demo's runbook uses it. Off unless typed: trusting
    the forwarded header on a directly-exposed box lets callers mint identities."""
    from megabrain.transports.cli.main import build_parser

    args = build_parser().parse_args(["ui", "--trust-proxy"])
    assert args.trust_proxy is True
    assert build_parser().parse_args(["ui"]).trust_proxy is False


def test_cache_reports_and_prunes(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The embedding cache never shrank and nothing showed its growth. `cache`
    makes it visible; `cache prune` is the explicit — never automatic — sweep."""
    import numpy as np

    from megabrain.providers.embeddings import EmbedCache

    monkeypatch.setenv("MEGABRAIN_HOME", str(tmp_path))
    EmbedCache().put("m", "text", np.ones(4, dtype=np.float32))
    assert "1 vector" in main_output(["cache"])
    pruned = main_output(["cache", "prune", "--older-than", "0"])
    assert "1 vector" in pruned
    assert EmbedCache().size() == (0, 0)


def main_output(argv: list[str]) -> str:
    import contextlib
    import io

    from megabrain.transports.cli.main import main

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert main(argv) == 0
    return out.getvalue()


def test_forge_is_registered_with_its_flags() -> None:
    from megabrain.transports.cli.main import build_parser

    args = build_parser().parse_args(["forge", ".", "--ext", "sql", "--dry-run",
                                      "--attempts", "2"])
    assert args.ext == "sql" and args.dry_run and args.attempts == 2
    assert args.run.__module__.endswith("commands.forge")
