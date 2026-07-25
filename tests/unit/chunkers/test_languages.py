"""Every language the build claims, held to the same three promises.

One parametrised suite rather than six files, because the promises do not vary:
the file parses, its declarations become symbols, a member is qualified by the
type that holds it, and the chunks are an exact line partition. A language that
cannot do all four is not supported — it is listed.

Each sample is written the way the language really is, not the way a test
fixture usually is: Ruby with `class << self`, Rust with an `impl`, PHP with a
namespace and a class constant, C with a struct beside its functions. Those are
exactly the shapes that broke the naive versions of these tables.
"""

from __future__ import annotations

import importlib.util
from typing import Callable, NamedTuple

import pytest

from megabrain.chunkers import c, cpp, csharp, go, java, php, ruby, rust
from megabrain.chunkers.cast import Chunker
from megabrain.chunkers.model import validate_partition

RUBY = """\
module Billing
  class Invoice
    def initialize(total)
      @total = total
    end

    def charge!
      @total
    end

    class << self
      def open_for(client)
        new(0)
      end
    end
  end
end
"""

GO = """\
package billing

import "fmt"

type Invoice struct {
	Total int
}

func New(total int) *Invoice {
	return &Invoice{Total: total}
}

func (i *Invoice) Charge() error {
	return fmt.Errorf("charged %d", i.Total)
}
"""

RUST = """\
pub struct Invoice {
    pub total: u32,
}

pub trait Chargeable {
    fn charge(&self) -> u32;
}

impl Chargeable for Invoice {
    fn charge(&self) -> u32 {
        self.total
    }
}

pub fn open_for(total: u32) -> Invoice {
    Invoice { total }
}
"""

PHP = """\
<?php

namespace App\\Billing;

class Invoice
{
    const CURRENCY = 'PEN';

    public function charge(int $total): int
    {
        return $total;
    }
}

function open_for(int $total): Invoice
{
    return new Invoice();
}
"""

C = """\
#include <stdio.h>

struct Invoice {
    int total;
};

int charge(struct Invoice *invoice) {
    return invoice->total;
}

static void report(int amount) {
    printf("%d\\n", amount);
}
"""

CPP = """\
#include <string>

namespace billing {

class Invoice {
public:
    explicit Invoice(int total) : total_(total) {}

    int charge() const { return total_; }

private:
    int total_;
};

int open_for(int total) { return Invoice(total).charge(); }

}  // namespace billing
"""

JAVA = """\
package app.billing;

public interface Chargeable {
    int charge();
}

public class Invoice implements Chargeable {
    private final int total;

    public Invoice(int total) {
        this.total = total;
    }

    @Override
    public int charge() {
        return total;
    }
}
"""

CSHARP = """\
namespace App.Billing;

public interface IChargeable
{
    int Charge();
}

public class Invoice : IChargeable
{
    private readonly int _total;

    public Invoice(int total)
    {
        _total = total;
    }

    public int Charge()
    {
        return _total;
    }
}
"""

class Case(NamedTuple):
    parse: Callable[[str, str], object]
    path: str
    source: str
    declares: set[str]        # names the file must yield, unqualified
    member: str | None        # a member that must come back QUALIFIED
    grammar: str              # the package its grammar needs

    def parsed(self) -> object:
        if importlib.util.find_spec(self.grammar) is None:
            pytest.skip(f"{self.grammar} is not installed")
        return self.parse(self.path, self.source)


CASES = [
    Case(ruby.parse, "billing/invoice.rb", RUBY, {"Billing", "Invoice"},
         "Invoice.charge!", "tree_sitter_ruby"),
    Case(go.parse, "billing/invoice.go", GO, {"Invoice", "New", "Charge"},
         None, "tree_sitter_go"),
    Case(rust.parse, "src/invoice.rs", RUST, {"Invoice", "Chargeable", "open_for"},
         "Invoice.charge", "tree_sitter_rust"),
    Case(php.parse, "src/Invoice.php", PHP, {"Invoice", "open_for"},
         "Invoice.charge", "tree_sitter_php"),
    Case(c.parse, "src/invoice.c", C, {"Invoice", "charge", "report"},
         None, "tree_sitter_c"),
    Case(cpp.parse, "src/invoice.cpp", CPP, {"Invoice", "open_for"},
         "Invoice.charge", "tree_sitter_cpp"),
    Case(java.parse, "app/Invoice.java", JAVA, {"Invoice", "Chargeable"},
         "Invoice.charge", "tree_sitter_java"),
    Case(csharp.parse, "App/Invoice.cs", CSHARP, {"Invoice", "IChargeable"},
         "Invoice.Charge", "tree_sitter_c_sharp"),
]

IDS = [case.path.rsplit(".", 1)[-1] for case in CASES]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_the_file_parses_and_names_what_it_declares(case: Case) -> None:
    result = case.parsed()
    assert result.ok is True                                # type: ignore[attr-defined]
    names = {symbol.name.rsplit(".", 1)[-1]                 # type: ignore[attr-defined]
             for symbol in result.symbols}                  # type: ignore[attr-defined]
    assert case.declares <= names, f"missing {case.declares - names}"


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_a_member_is_QUALIFIED_by_the_type_that_holds_it(case: Case) -> None:
    """`charge` alone is ambiguous in any repository with two of them."""
    if case.member is None:
        pytest.skip("this language's sample has no nested member to qualify")
    names = {symbol.name for symbol in case.parsed().symbols}  # type: ignore[attr-defined]
    # A SUFFIX check: Ruby qualifies through its module (`Billing.Invoice.charge!`)
    # and C++ through its namespace. Both are MORE qualified than asked for, which
    # is the promise kept — not a different one.
    assert any(name == case.member or name.endswith(f".{case.member}")
               for name in names), f"{case.member} not in {sorted(names)}"


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_the_chunks_are_an_exact_line_partition(case: Case) -> None:
    case.parsed()                     # skips here when the grammar is missing
    result = Chunker(case.parse).chunk_file(case.path, case.source)  # type: ignore[arg-type]
    assert validate_partition(result) == []


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_the_skeleton_holds_declarations_and_no_bodies(case: Case) -> None:
    skeleton = case.parsed().skeleton                       # type: ignore[attr-defined]
    assert "Invoice" in skeleton
    assert "return" not in skeleton, "a body leaked into the file-level vector"


def test_a_unit_can_never_end_PAST_the_last_line() -> None:
    """FOUND IN USE, on 16 files of a real index.

    A grammar reading a file it half-understands can report a node whose
    `end_point` is one line past the content — C++ parsed by the C grammar does
    it on `folly/Uri.h`, and so did PHP's mixed-HTML text nodes in the version
    this was ported from. The chunk then claims a line the file does not have,
    which breaks the partition invariant (hard rule #4) and puts a line number
    in a citation that cannot be opened.

    v2 clamped it in `segment()`. The port dropped the clamp, and only a sweep
    over 18 191 real headers surfaced it: the guarantee has to hold for a file
    the grammar gets WRONG, not just for one it gets right.
    """
    source = "namespace folly {\nclass Uri {};\n}\n#include <folly/Uri-inl.h>\n"
    total = len(source.split("\n")) - 1                  # the trailing \n is a terminator
    for parse in (c.parse, cpp.parse, java.parse, csharp.parse, go.parse,
                  rust.parse, ruby.parse, php.parse):
        parsed = parse("Uri.h", source)
        overruns = [(unit.name, unit.end_line) for unit in parsed.units
                    if unit.end_line > total]
        assert not overruns, f"{parse.__module__} reported {overruns} past L{total}"
