"""specialize toolkit (NO model): opportunity detection, the changed-files A/B
gate, and gate_strategy's install-only-on-measured-win rule. Offline via a
token-hash embedder."""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.forge import ab_gate, detect_specialization, gate_strategy
from megabrain.forge.changed import changed_files
from megabrain.forge.probes import probe_spans
from megabrain.indexing.trust import load_repo_strategies
from tests.unit.forge.fixtures import TokenEmbedder

_ENTRIES = "\n".join(
    f'    {100 + i}: (\n        "{w}_alpha",\n        "{w}_beta",\n'
    f'        "{w}_gamma",\n    ),'
    for i, w in enumerate(
        "aardvark bison caiman dugong echidna fossa gharial hoatzin ibex jerboa "
        "kinkajou lemur markhor numbat okapi pangolin quokka rhea serval tapir "
        "urial vicuna wombat xerus yapok zorilla axolotl bandicoot capybara "
        "dhole".split()))
TABLE_PY = f'"""Big lookup table."""\n\n_codes = {{\n{_ENTRIES}\n}}\n'
NORMAL_PY = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"


def _strategy(group: int, budget: int):  # type: ignore[no-untyped-def]
    """Reference shape-router: table files cut per `group` lines; everything
    else delegates to the built-in parse byte-identically."""
    from megabrain.chunkers import Parsed, Unit
    from megabrain.indexing.builtin import builtin_strategy_for

    class PySpecialStrategy:
        exts = (".py",)

        def __init__(self) -> None:
            self.budget = budget
            self._fallback = builtin_strategy_for(".py")

        def parse(self, relpath: str, source: str) -> Parsed:
            if "_codes = {" not in source:
                assert self._fallback is not None
                return self._fallback.parse(relpath, source)
            total = len(source.splitlines())
            first = next(i for i, line in enumerate(source.splitlines(), 1)
                         if "_codes = {" in line)
            cuts = [1, *range(first + 1, total, group)]
            bounds = list(zip(cuts, [c - 1 for c in cuts[1:]] + [total]))
            units = tuple(Unit(s, e, "block", f"L{s}-{e}") for s, e in bounds)
            return Parsed(units=units, symbols=(), skeleton=f"# {relpath}")

        def edge_context(self, sources: dict[str, str]) -> object:
            return None

        def edges(self, relpath: str, source: str, context: object) -> None:
            return None

    return PySpecialStrategy()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "table.py").write_text(TABLE_PY, encoding="utf-8")
    (tmp_path / "normal.py").write_text(NORMAL_PY, encoding="utf-8")
    (tmp_path / "other.py").write_text(NORMAL_PY.replace("add", "mul"),
                                       encoding="utf-8")
    return tmp_path


def test_detect_finds_the_data_table(repo: Path) -> None:
    opportunities = detect_specialization(repo)
    assert [o["ext"] for o in opportunities] == [".py"]
    assert opportunities[0]["target"] == "table.py"
    assert "dict/list literal" in opportunities[0]["diagnoses"]["table.py"]


def test_probe_spans_are_the_dict_entries(repo: Path) -> None:
    probes = probe_spans(repo / "table.py")
    assert len(probes) == 30
    assert all(a <= b for _, a, b in probes)
    assert "aardvark" in probes[0][0]


def test_changed_files_is_exactly_the_special_file(repo: Path) -> None:
    assert changed_files(repo, _strategy(group=10, budget=300)) == ["table.py"]


def test_gate_rejects_a_noop_candidate(repo: Path) -> None:
    from megabrain.indexing.builtin import builtin_strategy_for

    verdict = ab_gate(repo, builtin_strategy_for(".py"))  # type: ignore[arg-type]
    assert not verdict["win"] and verdict["reason"] == "candidate changes no files"


def test_gate_accepts_tight_and_rejects_coarse(repo: Path) -> None:
    tight = ab_gate(repo, _strategy(group=10, budget=300),
                    embedder=TokenEmbedder())
    assert tight["win"] and tight["delta_iou"] > 0
    assert tight["changed_files"] == ["table.py"]
    coarse = ab_gate(repo, _strategy(group=1000, budget=4000),
                     embedder=TokenEmbedder())
    assert not coarse["win"]


def test_gate_rejects_micro_chunking_outright(repo: Path) -> None:
    """1-line chunks have perfect span geometry and embed as noise — the
    granularity floor must reject them BEFORE any indexing happens."""
    verdict = ab_gate(repo, _strategy(group=1, budget=10),
                      embedder=TokenEmbedder())
    assert not verdict["win"]
    assert "degenerate granularity" in verdict["reason"]


_CODE = '''
from megabrain.chunkers import Parsed, Unit
from megabrain.indexing.builtin import builtin_strategy_for


class PySpecialStrategy:
    exts = (".py",)
    budget = {budget}

    def __init__(self):
        self._fallback = builtin_strategy_for(".py")

    def parse(self, relpath, source):
        if "_codes = {{" not in source:
            return self._fallback.parse(relpath, source)
        lines = source.splitlines()
        total = len(lines)
        first = next(i for i, ln in enumerate(lines, 1) if "_codes = {{" in ln)
        cuts = [1, *range(first + 1, total, {group})]
        bounds = list(zip(cuts, [c - 1 for c in cuts[1:]] + [total]))
        units = tuple(Unit(s, e, "block", f"L{{s}}-{{e}}") for s, e in bounds)
        return Parsed(units=units, symbols=(), skeleton=f"# {{relpath}}")

    def edge_context(self, sources):
        return None

    def edges(self, relpath, source, context):
        return None
'''


def test_gate_strategy_installs_a_winning_handwritten_strategy(repo: Path) -> None:
    report = gate_strategy(repo, _CODE.format(group=10, budget=300), ".py",
                           embedder=TokenEmbedder())
    assert report["gate"]["win"]
    assert report.get("installed") and (repo / ".megabrain/strategies/py.py").exists()
    assert [s for s in load_repo_strategies(repo) if ".py" in s.exts]


def test_gate_strategy_rejects_and_does_not_install_a_coarse_one(repo: Path) -> None:
    report = gate_strategy(repo, _CODE.format(group=1000, budget=4000), ".py",
                           embedder=TokenEmbedder())
    assert not report["gate"]["win"]
    assert "installed" not in report
    assert not (repo / ".megabrain/strategies/py.py").exists()
