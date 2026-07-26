"""TypeScript, JavaScript and their JSX variants.

FOUND IN USE, and it was the whole product failing: every repository somebody
actually wanted to index was TypeScript, and this build read `.py` only. The
census said so politely, which is not the same as working.

The grammar is tree-sitter; everything after it — the split-then-merge, the
partition guarantee, breadcrumbs, the skeleton — is the machinery Python
already goes through. A language contributes one function and nothing else.
"""

from __future__ import annotations

from megabrain.chunkers.cast import Chunker
from megabrain.chunkers.languages import typescript
from megabrain.chunkers.model import validate_partition

SERVICE = """\
import { Logger } from "./logger";
import type { Config } from "./config";

export const RETRIES = 3;

export interface Session {
  id: string;
  user: string;
}

export type Handler = (session: Session) => Promise<void>;

export class SessionService {
  private log = new Logger();

  constructor(private config: Config) {}

  async open(user: string): Promise<Session> {
    this.log.info(`opening for ${user}`);
    return { id: "1", user };
  }

  close(session: Session): void {
    this.log.info(`closing ${session.id}`);
  }
}

export default function boot(config: Config): SessionService {
  return new SessionService(config);
}

export const helper = (n: number) => n * 2;
"""


def parsed(source: str = SERVICE, relpath: str = "src/service.ts"):
    return typescript.parse(relpath, source)


def names(source: str = SERVICE) -> set[str]:
    return {symbol.name for symbol in parsed(source).symbols}


def test_a_typescript_file_parses_at_all() -> None:
    assert parsed().ok is True


def test_classes_functions_and_arrow_consts_are_all_symbols() -> None:
    """The three ways TypeScript declares a callable. Miss the arrow-function
    const and half of a modern codebase becomes unnameable."""
    found = names()
    assert {"SessionService", "boot", "helper", "RETRIES"} <= found


def test_TYPES_are_symbols_too() -> None:
    """An interface is what a TypeScript reader searches for most, and it has no
    Python equivalent — leaving it out would answer "where is Session defined"
    with the file that imports it."""
    assert {"Session", "Handler"} <= names()


def test_methods_are_qualified_by_their_class() -> None:
    """`open` alone is ambiguous in any repo with more than one service."""
    assert {"SessionService.open", "SessionService.close"} <= names()


def test_an_EXPORTED_declaration_is_not_hidden_by_its_export_wrapper() -> None:
    """`export class Foo` is a class. The grammar wraps it in an
    `export_statement`, and a walk that stops there finds no declarations at all
    — which is what an unported chunker looks like from the outside."""
    without = typescript.parse("plain.ts", SERVICE.replace("export ", ""))
    assert {s.name for s in without.symbols} <= names(), \
        "the same declarations, exported or not"
    assert "SessionService" in names()


def test_the_chunks_are_an_exact_line_partition() -> None:
    """Hard rule #4, and it is checked rather than trusted — the same oracle the
    Python chunker answers to."""
    result = Chunker(typescript.parse).chunk_file("src/service.ts", SERVICE)
    assert validate_partition(result) == []


def test_a_method_carries_a_breadcrumb_naming_its_class() -> None:
    result = Chunker(typescript.parse).chunk_file("src/service.ts", SERVICE)
    crumbs = " ".join(chunk.breadcrumb for chunk in result.chunks)
    assert "SessionService" in crumbs


def test_the_skeleton_is_declarations_not_bodies() -> None:
    """It is one vector per file, and a body in it would just re-embed what the
    chunks already say."""
    skeleton = parsed().skeleton
    assert "SessionService" in skeleton and "open" in skeleton
    assert "this.log.info" not in skeleton


def test_JSX_parses_with_the_tsx_grammar() -> None:
    """`.tsx` is not TypeScript — `<div>` is a syntax error to the plain
    grammar, and the whole file would fall back to line windows."""
    source = ("export function Card({ title }: { title: string }) {\n"
              "  return <div className=\"card\">{title}</div>;\n"
              "}\n")
    result = typescript.parse("ui/Card.tsx", source)
    assert result.ok is True and any(s.name == "Card" for s in result.symbols)


def test_plain_JAVASCRIPT_parses_too() -> None:
    source = ("const express = require('express');\n\n"
              "function makeApp() {\n  return express();\n}\n\n"
              "module.exports = { makeApp };\n")
    result = typescript.parse("server.js", source)
    assert result.ok is True and any(s.name == "makeApp" for s in result.symbols)


def test_a_COMMONJS_prototype_assignment_is_a_symbol() -> None:
    """`Route.prototype.dispatch = function () {}` is how half of npm declares a
    method. Without it those files hold no nameable symbol at all."""
    source = ("function Route() {}\n\n"
              "Route.prototype.dispatch = function dispatch(req) {\n"
              "  return req;\n"
              "};\n")
    assert any("dispatch" in symbol.name
               for symbol in typescript.parse("route.js", source).symbols)


SUITE = """\
const express = require('express');

describe('res.attachment()', function () {
  beforeEach(function () {
    this.app = express();
  });

  it('should Content-Disposition to attachment', function (done) {
    request(this.app).get('/').expect('Content-Disposition', 'attachment', done);
  });

  it('should add the filename param', function (done) {
    request(this.app).get('/').expect(200, done);
  });
});
"""


def test_a_MOCHA_case_is_a_symbol() -> None:
    """A suite declares its units by CALLING a function with a label and a
    closure, which the grammar reads as an expression statement. Express's
    `test/res.attachment.js` came back with two symbols, both `require`
    bindings, while the fifteen cases a reader edits were unnameable — and
    `_mentions` resolves a match to the symbol CONTAINING it, so no lane could
    return a row inside any test file in a JS repository."""
    found = names(SUITE)
    assert any("should add the filename param" in name for name in found)
    assert any("beforeEach" in name for name in found), "a hook is an edit site too"


def test_a_case_carries_the_LINES_of_its_own_body_not_the_files() -> None:
    """The range is the entire point: a row without one is a file to read, a row
    with one is a jump."""
    cases = [s for s in parsed(SUITE, "test/res.attachment.js").symbols
             if "filename param" in s.name]
    assert len(cases) == 1
    assert (cases[0].line, cases[0].end_line) == (12, 14)


def test_the_GROUP_is_not_a_symbol_so_it_cannot_swallow_its_cases() -> None:
    """`describe` spans the file, and `_idents.outermost` keeps the symbol no
    other symbol contains — so recording the group would drop every case inside
    it and hand back one row meaning "this file", which the reader already had."""
    assert not any(name.startswith("describe") for name in names(SUITE))


def test_a_call_that_is_not_a_test_is_not_a_symbol() -> None:
    """The label-plus-closure shape is what identifies a declaration here, so a
    plain call with a callback must stay invisible — otherwise every
    `app.get('/', handler)` in an Express app becomes a fake declaration."""
    source = ("const app = express();\n"
              "app.get('/users', function (req, res) { res.send('ok'); });\n")
    assert not any("users" in name
                   for name in {s.name for s in typescript.parse("a.js", source).symbols})


def test_a_file_that_does_not_parse_still_partitions() -> None:
    """Broken syntax is the normal state of a file somebody is editing. It must
    stay in the index as line windows rather than vanish."""
    result = Chunker(typescript.parse).chunk_file("broken.ts", "export class {{{ oops\n")
    assert validate_partition(result) == []


def test_an_empty_file_is_not_an_error() -> None:
    assert typescript.parse("empty.ts", "").ok is True
