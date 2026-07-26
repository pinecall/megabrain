"""A section whose every quote was already shown is dropped, not shortened.

A REGRESSION this engine introduced and both readers of the same round named in
the same words: deduplicating a repeated range into "— quoted above" was a win
of ~60 lines, but a section where EVERY citation is a repeat survives as a
heading over a list of back-references. "Zero information, and it re-costs the
reader's attention at exactly the point they're deciding what to write."
"""

from __future__ import annotations

from megabrain.ask._prune import prune_empty_sections

HOLLOW = """## lib/app.rb — the change
**`lib/app.rb` L1-9**
```ruby
def x
end
```

## Pattern to follow
**`lib/app.rb` L1-9** — quoted above
"""


def test_a_section_of_only_BACKREFS_is_dropped() -> None:
    """The measured regression, verbatim in shape."""
    out = prune_empty_sections(HOLLOW)
    assert "Pattern to follow" not in out


def test_the_section_that_CARRIED_the_code_survives() -> None:
    """Only the hollow one goes. Pruning the quote itself would be worse than
    the noise it removes."""
    out = prune_empty_sections(HOLLOW)
    assert "```ruby" in out and "def x" in out


def test_a_section_with_ONE_new_quote_survives() -> None:
    """Mixed sections keep their heading — the back-reference beside real code
    is the deduplication working, not an empty promise."""
    text = ("## Pattern to follow\n**`a.rb` L1-2** — quoted above\n"
            "**`b.rb` L1-2**\n```ruby\nreal\n```\n")
    assert "Pattern to follow" in prune_empty_sections(text)


def test_a_section_of_PROSE_survives() -> None:
    """An explanation with no code is still an explanation. Only a heading over
    nothing but repeats is hollow."""
    text = "## No change needed\nThe mechanism already covers it.\n"
    assert prune_empty_sections(text) == text


def test_the_specification_prose_under_a_backref_survives() -> None:
    """A back-reference followed by the spec of the change is the whole point
    of an anchor section — dropping it would delete the instruction."""
    text = ("## lib/app.rb — the change\n**`a.rb` L1-2** — quoted above\n"
            "APPLY insert_after\nAdd a sibling that does the thing.\n")
    assert "Add a sibling" in prune_empty_sections(text)
