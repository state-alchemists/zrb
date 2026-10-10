from zrb.util.string.fuzzy_match import find_fuzzy_match


def test_trailing_whitespace_drift_returns_the_content_block():
    content = "a = 1   \nb = 2\n"
    assert find_fuzzy_match(content, "a = 1\nb = 2") == "a = 1   \nb = 2\n"


def test_indentation_drift_returns_the_content_block():
    content = "def f():\n        x = 1\n        y = 2\n"
    assert find_fuzzy_match(content, "x = 1\ny = 2") == "        x = 1\n        y = 2\n"


def test_single_line_indent_shift_is_not_matched():
    assert find_fuzzy_match("    x = 1\n", "x = 1") is None


def test_no_match_returns_none():
    assert find_fuzzy_match("a\nb\n", "c\nd") is None


def test_empty_old_text_returns_none():
    assert find_fuzzy_match("a\n", "") is None
