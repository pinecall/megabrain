"""Do MAX_BARE and MAX_TESTS hold outside the three repos they were tuned on?

The claim under test: a one-word name that is the TARGET of a task resolves to a
handful of implementation sites, while one that is merely the CONTAINER resolves
to many. If that separation only exists in click/express/sinatra, the number is
overfitted and should be said so.
"""
from __future__ import annotations

import json
import pathlib
import statistics

from megabrain.grep.idents import specific
from megabrain.grep.mentions import _for_one
from megabrain.grep.spread import MAX_BARE
from megabrain.storage import Store

registry = json.loads((pathlib.Path.home()/".megabrain/registry.json").read_text())
rows: list[tuple[str, str, int, bool]] = []

# The survey population: real repositories, not the scratch indexes a dev
# accumulates. Edit this to re-run it on yours.
REAL = ("click", "ex-mb", "bench-express", "sinatra", "shipway", "webrtc", "sdk",
        "pinecall", "aldus-v2", "LumiCRM", "pineward", "vscode-js-debug",
        "megabrain-v2", "megabrain-v3", "anthropic-sdk-python", "graphify")
for root in sorted(registry):
    if not pathlib.Path(root, ".megabrain").exists():
        continue
    if pathlib.Path(root).name not in REAL:
        continue
    try:
        with Store(root) as store:
            counts = store.symbols.name_counts()
            texts = [(m.file, m.text or "", m.start_line) for m in store.chunks.read_metas()]
            if not texts:
                continue
            # every ONE-WORD name the repo declares, which is the population the
            # threshold judges
            bare = [n for n, c in counts.items()
                    if not specific(n) and len(n) >= 4 and 0 < c <= 12]
            declared: dict[str, list] = {}
            for name in sorted(bare)[:120]:          # bounded: this is a survey
                sites = _for_one(store, name, texts, declared)
                code = sum(1 for _, is_test in sites if not is_test)
                rows.append((pathlib.Path(root).name, name, code, code <= MAX_BARE))
    except Exception as exc:                                    # noqa: BLE001
        print(f"  skip {root}: {type(exc).__name__}")

by_repo: dict[str, list[int]] = {}
for repo, _name, code, _ok in rows:
    by_repo.setdefault(repo, []).append(code)

print(f"MAX_BARE = {MAX_BARE}; {len(rows)} one-word names across {len(by_repo)} repos\n")
print(f"{'repo':22s} {'names':>6s} {'median':>7s} {'p90':>5s} {'max':>5s} {'<=MAX_BARE':>11s}")
for repo, counts in sorted(by_repo.items()):
    counts.sort()
    p90 = counts[int(len(counts) * 0.9)] if counts else 0
    kept = sum(1 for c in counts if c <= MAX_BARE)
    print(f"{repo:22s} {len(counts):6d} {statistics.median(counts):7.1f} {p90:5d} "
          f"{max(counts):5d} {100*kept//len(counts):10d}%")

allc = sorted(c for cs in by_repo.values() for c in cs)
print(f"\nGLOBAL: median {statistics.median(allc):.1f} · "
      f"p90 {allc[int(len(allc)*0.9)]} · p99 {allc[int(len(allc)*0.99)]} · max {max(allc)}")
print(f"a threshold of {MAX_BARE} keeps "
      f"{100*sum(1 for c in allc if c <= MAX_BARE)//len(allc)}% of one-word names")
