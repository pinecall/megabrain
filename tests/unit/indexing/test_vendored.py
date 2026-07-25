"""Dependency trees that are not the repository.

FOUND IN USE the day C and C++ were added. Indexing a React Native project
walked `ios/Pods` and swallowed **17 864 headers** — boost, folly, prebuilt
React frameworks — so a 400-file repo came back as 19 575 files, took seven
minutes, and buried its own source under vendored template metaprogramming.

`node_modules` and `vendor` were already excluded; the mobile ecosystems have
their own names for the same thing, and nothing that ships a `Podfile` is
asking for its pods to be searchable.
"""

from __future__ import annotations

from pathlib import Path

from megabrain.indexing import discover
from megabrain.indexing.builtin import default_registry
from tests.unit.indexing.fake import write

VENDORED = {
    "src/app.ts": "export const run = () => 1;\n",
    "ios/Pods/boost/mpl/aux_/fold_impl.hpp": "template <class T> struct fold {};\n",
    "ios/Pods/Headers/Public/React/primitives.h": "struct Prim {};\n",
    "android/.gradle/cache/thing.java": "class Thing {}\n",
    "ios/build/DerivedData/x.h": "struct X {};\n",
    "third_party/zlib/zlib.h": "struct Z {};\n",
    "Carthage/Build/iOS/Frame.h": "struct F {};\n",
    "src/native/real.h": "struct Real {};\n",
}


def found(root: Path) -> set[str]:
    write(root, VENDORED)
    registry = default_registry()
    return {entry.relpath for entry in discover(root, registry.extensions).files}


def test_cocoapods_headers_are_NOT_the_repository(tmp_path: Path) -> None:
    """The finding, by name: 17 864 of them in one project."""
    assert not any(path.startswith("ios/Pods/") for path in found(tmp_path))


def test_the_projects_OWN_native_headers_are_kept(tmp_path: Path) -> None:
    """The exclusion is about DEPENDENCY trees, not about C. A header the
    project wrote is source like any other."""
    assert "src/native/real.h" in found(tmp_path)


def test_every_ecosystems_dependency_directory_is_excluded(tmp_path: Path) -> None:
    kept = found(tmp_path)
    for buried in ("android/.gradle/cache/thing.java", "ios/build/DerivedData/x.h",
                   "third_party/zlib/zlib.h", "Carthage/Build/iOS/Frame.h"):
        assert buried not in kept, f"{buried} was indexed"


def test_the_repositorys_own_source_survives_all_of_it(tmp_path: Path) -> None:
    assert "src/app.ts" in found(tmp_path)
