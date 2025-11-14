from zrb.util.markdown import (
    demote_markdown_headers,
    make_markdown_section,
    promote_markdown_headers,
)


# Test cases for _demote_markdown_headers
def test_demote_markdown_headers_simple():
    content = "# Header 1\n## Header 2"
    expected = "## Header 1\n### Header 2"
    assert demote_markdown_headers(content) == expected


def test_demote_markdown_headers_no_headers():
    content = "This is a simple text."
    expected = "This is a simple text."
    assert demote_markdown_headers(content) == expected


def test_demote_markdown_headers_in_code_block():
    content = "```\n# This is a header in a code block\n```"
    expected = "```\n# This is a header in a code block\n```"
    assert demote_markdown_headers(content) == expected


def test_demote_markdown_headers_nested_code_block():
    content = "````\n```\n# Header in nested block\n```\n````"
    expected = "````\n```\n# Header in nested block\n```\n````"
    assert demote_markdown_headers(content) == expected


def test_demote_markdown_headers_mixed_content():
    content = (
        "# Real Header\n"
        "Some text\n"
        "```python\n"
        "# Not a real header\n"
        "print('hello')\n"
        "```\n"
        "## Another Real Header"
    )
    expected = (
        "## Real Header\n"
        "Some text\n"
        "```python\n"
        "# Not a real header\n"
        "print('hello')\n"
        "```\n"
        "### Another Real Header"
    )
    assert demote_markdown_headers(content) == expected


# Test cases for promote_markdown_headers
def test_promote_markdown_headers_simple():
    content = "## Header 1\n### Header 2"
    expected = "# Header 1\n## Header 2"
    assert promote_markdown_headers(content) == expected


def test_promote_markdown_headers_no_headers():
    content = "This is a simple text."
    expected = "This is a simple text."
    assert promote_markdown_headers(content) == expected


def test_promote_markdown_headers_in_code_block():
    content = "```\n## This is a header in a code block\n```"
    expected = "```\n## This is a header in a code block\n```"
    assert promote_markdown_headers(content) == expected


def test_promote_markdown_headers_level_one():
    content = "# Header 1"
    expected = "# Header 1"
    assert promote_markdown_headers(content) == expected


def test_promote_markdown_headers_mixed_content():
    content = (
        "## Real Header\n"
        "Some text\n"
        "```python\n"
        "### Not a real header\n"
        "print('hello')\n"
        "```\n"
        "### Another Real Header"
    )
    expected = (
        "# Real Header\n"
        "Some text\n"
        "```python\n"
        "### Not a real header\n"
        "print('hello')\n"
        "```\n"
        "## Another Real Header"
    )
    assert promote_markdown_headers(content) == expected


# Test cases for make_prompt_section
def test_make_prompt_section_empty_content():
    result = make_markdown_section("Empty", "   ")
    assert result == ""


def test_make_prompt_section_not_as_code():
    header = "Test Header"
    content = "# A Title\nSome text."
    expected = "# Test Header\n## A Title\nSome text.\n"
    result = make_markdown_section(header, content, as_code=False)
    assert result == expected


def test_make_prompt_section_as_code_simple():
    header = "Code Block"
    content = "print('hello')"
    expected = "# Code Block\n````\nprint('hello')\n````\n"
    result = make_markdown_section(header, content, as_code=True)
    assert result == expected


def test_make_prompt_section_as_code_with_backticks():
    header = "Code with Ticks"
    content = "Here is some code: ```python\nprint('hello')\n```"
    expected = (
        "# Code with Ticks\n"
        "````\n"
        "Here is some code: ```python\nprint('hello')\n```\n"
        "````\n"
    )
    result = make_markdown_section(header, content, as_code=True)
    assert result == expected


def test_make_prompt_section_as_code_with_four_backticks():
    header = "Code with Four Ticks"
    content = "Code block: ````\nThis is tricky\n````"
    expected = (
        "# Code with Four Ticks\n"
        "`````\n"
        "Code block: ````\nThis is tricky\n````\n"
        "`````\n"
    )
    result = make_markdown_section(header, content, as_code=True)
    assert result == expected


def test_make_prompt_section_as_code_with_mixed_backticks():
    header = "Code with Mixed Ticks"
    content = "Block 1: ```\nCode\n```\nBlock 2: `````\nMore Code\n`````"
    # The longest sequence is 5, so the fence should be 6
    expected_fence = "`" * 6
    expected = (
        f"# {header}\n"
        f"{expected_fence}\n"
        f"{content.strip()}\n"
        f"{expected_fence}\n"
    )
    result = make_markdown_section(header, content, as_code=True)
    assert result == expected
