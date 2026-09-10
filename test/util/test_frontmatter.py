"""Tests for `zrb.util.frontmatter`.

The shared parser behind `SKILL.md` and `*.agent.md` loading. Both loaders used
to open-code the same three steps, and one copy lived inside a function already
at complexity 18.
"""

import pytest
import yaml

from zrb.util.frontmatter import parse_frontmatter


def test_parses_the_mapping_and_strips_the_body():
    content = "---\nname: review\ndescription: Review code\n---\n\n# Body\n\ntext\n"

    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {"name": "review", "description": "Review code"}
    assert body == "# Body\n\ntext"


def test_a_file_without_frontmatter_keeps_its_whole_content_as_body():
    content = "# Just markdown\n\nno header here\n"

    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {}
    assert body == content


def test_an_unterminated_block_is_not_frontmatter():
    """A lone `---` opener has no closing delimiter, so there is nothing to parse.

    Returning the content untouched lets the caller's H1 fallback still name the
    skill, which is a better outcome than discarding the file.
    """
    frontmatter, body = parse_frontmatter("---\nname: broken\n")

    assert frontmatter == {}
    assert body == "---\nname: broken\n"


def test_a_scalar_frontmatter_yields_an_empty_mapping():
    """`.get()` must be safe without a guard, so a non-mapping is normalized.

    The body is still recovered — the delimiters were well-formed.
    """
    frontmatter, body = parse_frontmatter("---\njust a string\n---\nbody\n")

    assert frontmatter == {}
    assert body == "body"


def test_malformed_yaml_raises_rather_than_reading_as_absent():
    """A syntax error is reported, not silently treated as "no frontmatter".

    Both callers already wrap loading in try/except and log a warning, so the
    file is skipped with a diagnosable message. Swallowing it here would make a
    typo'd `SKILL.md` load with default values and no signal.
    """
    with pytest.raises(yaml.YAMLError):
        parse_frontmatter("---\nname: [unclosed\n---\nbody\n")
