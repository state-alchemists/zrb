import pytest

from zrb.util.markdown import get_first_heading


@pytest.mark.parametrize(
    "content, expected",
    [
        ("# Title\nbody", "Title"),
        ("intro\n\n# Title  \n", "Title"),
        ("   # Up to three spaces", "Up to three spaces"),
        ("## Only a subheading\n", None),
        ("no heading at all", None),
        ("#NoSpace", None),
    ],
    ids=["first-line", "later-line", "three-space-indent", "h2-only", "none", "no-space"],
)
def test_get_first_heading_recognizes_atx_h1(content, expected):
    assert get_first_heading(content) == expected


def test_get_first_heading_skips_an_indented_code_block():
    content = "Example:\n\n    # not a heading\n\n# Real Title\n"
    assert get_first_heading(content) == "Real Title"


def test_get_first_heading_skips_a_tab_indented_line():
    assert get_first_heading("\t# code\n# Real Title") == "Real Title"


@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_get_first_heading_skips_fenced_code(fence):
    content = f"{fence}bash\n# install deps\npip install x\n{fence}\n# Real Title\n"
    assert get_first_heading(content) == "Real Title"


def test_get_first_heading_needs_a_matching_fence_to_close():
    content = "````\n```\n# still code\n````\n# Real Title"
    assert get_first_heading(content) == "Real Title"


def test_get_first_heading_in_an_unclosed_fence_is_none():
    assert get_first_heading("```\n# never closed") is None
