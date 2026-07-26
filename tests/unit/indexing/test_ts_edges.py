"""Resolving a TypeScript import to a file.

The graph's whole existence for a TS repository. Getting this wrong does not
fail — it yields a repository with no edges, which looks exactly like a
repository with no structure.

Three rules earn their tests below. A relative specifier names a file that may
be written six ways; a BARE specifier is a package and must never resolve to
something in this repo that shares a name; and `./thing.js` in a correctly
written ESM TypeScript project means `./thing.ts`, which is how most modern
repos are written and how a naive resolver finds nothing.
"""

from __future__ import annotations

from megabrain.indexing.edges import ts_edges, ts_files

FILES = {
    "src/app.ts": "",
    "src/logger.ts": "",
    "src/util/index.ts": "",
    "src/ui/Card.tsx": "",
    "src/legacy.js": "",
    "src/types.d.ts": "",
}


def edges(source: str, relpath: str = "src/app.ts") -> set[str]:
    return {target for target, _kind in ts_edges(relpath, source, ts_files(FILES))}


def test_a_named_import_resolves_without_its_extension() -> None:
    assert edges('import { log } from "./logger";') == {"src/logger.ts"}


def test_a_DIRECTORY_import_resolves_through_its_index_file() -> None:
    assert edges('import { help } from "./util";') == {"src/util/index.ts"}


def test_a_JS_specifier_resolves_to_the_TS_file_beside_it() -> None:
    """ESM requires the extension in the import and TypeScript compiles `.ts` to
    `.js`, so a correct TS project writes `./logger.js` and MEANS `./logger.ts`.
    Without this rule a modern repository yields almost no edges at all."""
    assert edges('import { log } from "./logger.js";') == {"src/logger.ts"}


def test_a_TSX_component_resolves() -> None:
    assert edges('import Card from "./ui/Card";') == {"src/ui/Card.tsx"}


def test_a_parent_relative_import_resolves() -> None:
    assert edges('import { log } from "../logger";',
                 relpath="src/ui/Panel.tsx") == {"src/logger.ts"}


def test_a_BARE_specifier_is_a_package_and_resolves_to_nothing() -> None:
    """`react` is not a file in this repository. An edge to something that
    merely shares a name is worse than the missing edge — it puts a dependency
    on the map that does not exist."""
    assert edges('import React from "react";\nimport { z } from "zod";') == set()


def test_a_SIDE_EFFECT_import_counts() -> None:
    """`import "./logger"` is a dependency: the module runs."""
    assert edges('import "./logger";') == {"src/logger.ts"}


def test_a_RE_EXPORT_counts() -> None:
    """A barrel file is nothing but re-exports, and it is exactly the file whose
    dependencies a reader wants to see."""
    assert edges('export { log } from "./logger";') == {"src/logger.ts"}
    assert edges('export * from "./logger";') == {"src/logger.ts"}


def test_a_COMMONJS_require_counts() -> None:
    assert edges('const { log } = require("./logger");') == {"src/logger.ts"}


def test_a_DYNAMIC_import_counts() -> None:
    assert edges('const mod = await import("./logger");') == {"src/logger.ts"}


def test_a_TYPE_ONLY_import_still_counts() -> None:
    """It disappears at runtime and is still a dependency in every sense a
    reader cares about: change the type and this file changes."""
    assert edges('import type { Config } from "./types";') == {"src/types.d.ts"}


def test_a_file_never_depends_on_ITSELF() -> None:
    assert edges('import { x } from "./app";') == set()


def test_the_same_module_imported_twice_is_ONE_edge() -> None:
    source = 'import { a } from "./logger";\nimport { b } from "./logger.js";'
    assert edges(source) == {"src/logger.ts"}


def test_an_unresolvable_relative_import_is_dropped_not_guessed() -> None:
    assert edges('import { x } from "./nope/missing";') == set()
