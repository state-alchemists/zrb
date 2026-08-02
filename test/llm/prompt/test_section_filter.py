"""A composed prompt never references a section it does not carry."""

from zrb.llm.prompt.section_filter import filter_requires


def test_block_survives_when_its_dependency_is_present():
    text = (
        "before\n"
        "<!--requires:journal_mandate-->\n"
        "search the journal\n"
        "<!--/requires-->\n"
        "after\n"
    )
    assert filter_requires(text, {"journal_mandate"}) == (
        "before\nsearch the journal\nafter\n"
    )


def test_block_is_dropped_when_its_dependency_is_absent():
    text = (
        "before\n"
        "<!--requires:journal_mandate-->\n"
        "search the journal\n"
        "<!--/requires-->\n"
        "after\n"
    )
    assert "journal" not in filter_requires(text, {"workflow"})


def test_all_listed_dependencies_must_be_present():
    text = "<!--requires:a,b-->\nkeep\n<!--/requires-->\n"
    assert filter_requires(text, {"a", "b"}) == "keep\n"
    assert filter_requires(text, {"a"}) == ""


def test_multiple_blocks_are_resolved_independently():
    text = (
        "<!--requires:a-->\nAAA\n<!--/requires-->\n"
        "middle\n"
        "<!--requires:b-->\nBBB\n<!--/requires-->\n"
    )
    out = filter_requires(text, {"a"})
    assert "AAA" in out
    assert "BBB" not in out
    assert "middle" in out


def test_unmarked_text_is_returned_unchanged():
    text = "# Heading\n\nA paragraph with a <!-- normal comment -->.\n"
    assert filter_requires(text, {"anything"}) == text


def test_marker_lines_never_survive():
    text = "<!--requires:a-->\nkept\n<!--/requires-->\n"
    out = filter_requires(text, {"a"})
    assert "requires" not in out
    assert "<!--" not in out


def test_dropping_a_block_does_not_leave_a_gap():
    text = "para one\n\n<!--requires:x-->\ngone\n<!--/requires-->\n\npara two\n"
    assert filter_requires(text, set()) == "para one\n\npara two\n"


def test_unterminated_block_is_kept_rather_than_swallowing_the_rest():
    """An authoring slip must not truncate the prompt to nothing."""
    text = "before\n<!--requires:a-->\nbody\nmore body\n"
    out = filter_requires(text, set())
    assert "before" in out
    assert "body" in out


def test_whitespace_in_the_marker_is_tolerated():
    text = "<!-- requires: a , b -->\nkept\n<!-- /requires -->\n"
    assert filter_requires(text, {"a", "b"}) == "kept\n"


def test_indented_marker_is_recognised():
    text = "  <!--requires:a-->\n  kept\n  <!--/requires-->\n"
    out = filter_requires(text, {"a"})
    assert "kept" in out
    assert "requires" not in out


def test_inline_marker_keeps_the_line_it_sits_in():
    """A conditional clause inside a sentence must not take the sentence with it."""
    text = "- A rule ends here.<!--requires:journal_mandate--> Journal writes are silent.<!--/requires-->\n"
    assert filter_requires(text, {"journal_mandate"}) == (
        "- A rule ends here. Journal writes are silent.\n"
    )
    assert filter_requires(text, set()) == "- A rule ends here.\n"


def test_block_and_inline_markers_coexist():
    text = (
        "intro<!--requires:a--> plus a clause<!--/requires-->\n"
        "<!--requires:b-->\nwhole line\n<!--/requires-->\n"
        "tail\n"
    )
    assert filter_requires(text, {"a"}) == "intro plus a clause\ntail\n"
    assert filter_requires(text, {"b"}) == "intro\nwhole line\ntail\n"
