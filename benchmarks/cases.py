"""The tasks measured, and the sites a reader actually has to open for each.

The ground truth is stated by SYMBOL, never by line number. Line numbers rot the
moment upstream lands a commit, and a benchmark whose expectations rot silently
starts reporting whatever it happens to still match. `measure.py` resolves each
symbol to its real range through the index, so a bumped pin changes the numbers
and never the claims.

Every site here was arrived at by making the change by hand, not by reading
either tool's output — otherwise the benchmark grades the tools against
themselves. `grep` is the literal search an agent actually types for the task,
which is the thing being compared against.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Case", "CASES"]


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    dirname: str
    task: str
    grep: str
    """The literal an agent types. One word, because that is what people run."""
    sites: tuple[tuple[str, str, str], ...]
    """(path, symbol, why it has to be opened)."""


CASES: tuple[Case, ...] = (
    Case(
        name="click", dirname="click", grep="show_envvar",
        task="Option has show_envvar; add show_envvar_value",
        sites=(
            ("src/click/core.py", "Option.__init__",
             "declare the new keyword argument"),
            ("src/click/core.py", "Option.get_help_extra",
             "where the flag has to be read for it to do anything"),
            ("src/click/types.py", "OptionHelpExtra",
             "the TypedDict the extra flows through — gains a key. Its text never "
             "contains `show_envvar`, so no literal search can reach it"),
            ("tests/test_options.py", "test_show_envvar",
             "the test to imitate"),
        ),
    ),
    Case(
        name="express", dirname="bench-express", grep="attachment",
        task="add res.inline beside res.attachment",
        sites=(
            ("lib/response.js", "res.attachment",
             "the sibling to copy, header for header"),
            ("test/res.attachment.js", "it should Content-Disposition to attachment",
             "the suite to imitate — a mocha case, invisible to a symbol table "
             "that only knows declarations"),
        ),
    ),
    Case(
        name="sinatra", dirname="sinatra", grep="send_file",
        task="add send_data beside send_file",
        sites=(
            ("lib/sinatra/base.rb", "Sinatra.Helpers.send_file",
             "the sibling to copy"),
        ),
    ),
)
