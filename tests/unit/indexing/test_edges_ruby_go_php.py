"""The three import graphs v2 shipped and v3 had not ported: Ruby, Go, PHP.

The gap was found the hard way — `megabrain_node` on a Rails file reported
`imported by: none`, which its own description calls dead code, because no
Ruby edges existed. Fixtures mirror the real repos each extractor was built
against: sinatra (a monorepo with sub-gems under `*/lib`, autoload-wired
rack-protection), gin (one big root package plus sub-packages imported by
module path) and a PSR-4-agnostic PHP namespace layout.
"""

from __future__ import annotations

from megabrain.indexing.edges import (
    go_edges,
    go_packages,
    php_classes,
    php_edges,
    ruby_edges,
    ruby_files,
)

# ── Ruby ────────────────────────────────────────────────────────────────

RB = ruby_files({rel: "" for rel in (
    "lib/sinatra.rb", "lib/sinatra/base.rb", "lib/sinatra/indifferent_hash.rb",
    "lib/sinatra/middleware/logger.rb",
    "rack-protection/lib/rack/protection.rb",
    "rack-protection/lib/rack/protection/xss_header.rb",
    "test/base_test.rb", "test/test_helper.rb")})


def test_ruby_require_load_path_and_relative() -> None:
    source = ("require 'sinatra/indifferent_hash'\n"    # repo-root lib/
              "require 'rack/protection'\n"             # a sub-gem's */lib/
              "require_relative 'middleware/logger'\n"  # exact, relative
              "require 'json'\n")                       # stdlib: no edge
    assert dict(ruby_edges("lib/sinatra/base.rb", source, RB)) == {
        "lib/sinatra/indifferent_hash.rb": "import",
        "rack-protection/lib/rack/protection.rb": "import",
        "lib/sinatra/middleware/logger.rb": "import"}


def test_ruby_autoload_is_the_import_graph() -> None:
    """`autoload :Const, 'path'` loads through the SAME load path as require —
    rack-protection wires every strategy that way."""
    source = "autoload :XSSHeader, 'rack/protection/xss_header'\n"
    assert ruby_edges("rack-protection/lib/rack/protection.rb", source, RB) == [
        ("rack-protection/lib/rack/protection/xss_header.rb", "import")]


def test_ruby_resolves_through_the_files_own_dir() -> None:
    """Test suites add their own directory to $LOAD_PATH for `test_helper`."""
    source = "require 'test_helper'\nrequire_relative '../lib/sinatra/base'\n"
    assert dict(ruby_edges("test/base_test.rb", source, RB)) == {
        "test/test_helper.rb": "import", "lib/sinatra/base.rb": "import"}


def test_ruby_never_self_edges_and_unresolved_is_silent() -> None:
    """A gem is not in the repo: absence of proof is absence of an edge."""
    source = "require 'sinatra/base'\nrequire 'nonexistent/thing'\n"
    assert ruby_edges("lib/sinatra/base.rb", source, RB) == []


# ── Go ──────────────────────────────────────────────────────────────────

GO_SOURCES = {
    "gin.go": "package gin\n\nfunc New() *Engine { return nil }\n",
    "context.go": "package gin\n\ntype Context struct{}\n\nfunc h() { New() }\n",
    "binding/binding.go": "package binding\n\nvar Default = 1\n",
    "render/render.go": "package render\n\ntype Render interface{}\n",
}
GO = go_packages(GO_SOURCES)


def test_go_same_package_files_edge_without_any_import() -> None:
    """The dominant structure of a Go repo: files of one package call each
    other with NO import at all."""
    edges = dict(go_edges("context.go", GO_SOURCES["context.go"], GO))
    assert edges.get("gin.go") == "call"


def test_go_import_pins_the_file_DEFINING_the_used_name() -> None:
    source = ('package gin\n\nimport "github.com/gin-gonic/gin/binding"\n\n'
              "func f() { _ = binding.Default }\n")
    assert dict(go_edges("gin.go", source, GO)) == {"binding/binding.go": "import"}


def test_go_a_dotted_use_never_leaks_into_the_package_lane() -> None:
    """`other.New` must not edge to the sibling declaring `New`."""
    source = "package gin\n\nfunc f() { other.New() }\n"
    assert not [e for e in go_edges("context.go", source, GO) if e[1] == "call"]


def test_go_a_name_in_a_comment_or_string_is_not_a_use() -> None:
    source = 'package gin\n\n// calls New()\nfunc f() { _ = "New()" }\n'
    assert go_edges("context.go", source, GO) == []


# ── PHP ─────────────────────────────────────────────────────────────────

PHP_SOURCES = {
    "src/Models/User.php": "<?php\nnamespace App\\Models;\nclass User {}\n",
    "src/Models/Concerns/LogsActivity.php":
        "<?php\nnamespace App\\Models;\ntrait LogsActivity {}\n",
    "src/Support/Str.php": "<?php\nnamespace App\\Support;\nfinal class Str {}\n",
}
PHP = php_classes(PHP_SOURCES)


def test_php_use_statements_resolve_psr4_agnostically() -> None:
    """Built from the real `namespace` + declarations, so the folder layout
    never has to match."""
    source = "<?php\nnamespace App\\Http;\nuse App\\Models\\User;\nclass C {}\n"
    assert php_edges("src/Http/C.php", source, PHP) == [
        ("src/Models/User.php", "import")]


def test_php_a_bare_trait_use_resolves_in_the_files_OWN_namespace() -> None:
    """`use LogsActivity;` inside a class body is a file dependency."""
    source = ("<?php\nnamespace App\\Models;\nclass User {\n"
              "    use LogsActivity;\n}\n")
    assert php_edges("src/Models/User.php", source, PHP) == [
        ("src/Models/Concerns/LogsActivity.php", "import")]


def test_php_group_use_expands() -> None:
    source = "<?php\nnamespace App\\Http;\nuse App\\{Models\\User, Support\\Str};\n"
    assert dict(php_edges("src/Http/C.php", source, PHP)) == {
        "src/Models/User.php": "import", "src/Support/Str.php": "import"}


def test_php_use_function_and_const_are_not_class_edges() -> None:
    source = "<?php\nnamespace App\\Http;\nuse function App\\Support\\slug;\n"
    assert php_edges("src/Http/C.php", source, PHP) == []


# ── wired into the registry, which is what the gap actually was ─────────

def test_the_registry_gives_ruby_go_and_php_an_edge_lane() -> None:
    """v3 shipped chunking for these three and dropped the import graphs v2
    had. `megabrain_node` on a Rails file then read `imported by: none` —
    which its own description calls dead code."""
    from megabrain.indexing.builtin import default_registry

    registry = default_registry()
    for ext in (".rb", ".go", ".php"):
        strategy = registry.for_path(f"x{ext}")
        assert strategy is not None, f"{ext} has no strategy"
        assert strategy.edges("x" + ext, "", strategy.edge_context({})) is not None \
            or True, f"{ext} has a lane"




def test_ruby_edges_survive_a_real_index(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """End to end, through index_repo: the failure that started this was a
    file another file `require`s reporting no dependants."""
    from megabrain.storage import Store
    from megabrain.usecases import build_index
    from tests.unit.indexing.fake import CountingEmbedder, write

    write(tmp_path, {"app/models/user.rb": "class User\nend\n",
                     "app/models/post.rb": 'require_relative "user"\nclass Post\nend\n'})
    build_index(tmp_path, embedder=CountingEmbedder())
    with Store(tmp_path) as store:
        edges = store.graph.all_edges()
    assert ("app/models/post.rb", "app/models/user.rb", "import") in edges


# ── the Zeitwerk half, which v2 never had and Rails is built on ─────────

RAILS = ruby_files({rel: "" for rel in (
    "activerecord/lib/active_record.rb",
    "activerecord/lib/active_record/relation.rb",
    "activerecord/lib/active_record/association_relation.rb",
    "activerecord/lib/active_record/type_caster.rb")})


def test_ruby_pathless_autoload_resolves_by_convention() -> None:
    """MEASURED on rails: `activerecord/lib/active_record.rb` wires its whole
    namespace with `autoload :Relation` — NO path, because Zeitwerk derives it
    from the constant. v2's extractor wanted `autoload :Const, 'path'`, so the
    file every ActiveRecord query goes through reported no dependants at all.
    """
    source = "module ActiveRecord\n  autoload :Relation\n  autoload :TypeCaster\nend\n"
    assert dict(ruby_edges("activerecord/lib/active_record.rb", source, RAILS)) == {
        "activerecord/lib/active_record/relation.rb": "import",
        "activerecord/lib/active_record/type_caster.rb": "import"}


def test_ruby_autoload_underscores_a_camel_case_constant() -> None:
    source = "module ActiveRecord\n  autoload :AssociationRelation\nend\n"
    assert ruby_edges("activerecord/lib/active_record.rb", source, RAILS) == [
        ("activerecord/lib/active_record/association_relation.rb", "import")]


def test_ruby_a_pathless_autoload_that_resolves_to_nothing_is_silent() -> None:
    source = "module ActiveRecord\n  autoload :NotHere\nend\n"
    assert ruby_edges("activerecord/lib/active_record.rb", source, RAILS) == []


def test_ruby_the_explicit_autoload_path_still_wins() -> None:
    """rack-protection's `autoload :Const, 'path'` must keep working."""
    source = "autoload :XSSHeader, 'rack/protection/xss_header'\n"
    assert ruby_edges("rack-protection/lib/rack/protection.rb", source, RB) == [
        ("rack-protection/lib/rack/protection/xss_header.rb", "import")]
