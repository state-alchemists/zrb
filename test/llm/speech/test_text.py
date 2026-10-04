import pytest

from zrb.llm.speech.text import clean_for_speech, fill_template


def test_clean_drops_code_tables_urls_and_markup():
    reply = """# Result

Run `pytest` now. See [the docs](https://example.com/docs) or https://x.io.

```python
print("never read aloud")
```

| name | value |
| --- | --- |
| a | 1 |

- **Done** 🎉
"""
    spoken = clean_for_speech(reply)

    assert "print" not in spoken
    assert "|" not in spoken and "value" not in spoken
    assert "http" not in spoken
    assert "#" not in spoken and "**" not in spoken and "🎉" not in spoken
    assert "Run pytest now" in spoken
    assert "the docs" in spoken
    assert "Done" in spoken


def test_clean_turns_arrows_and_dashes_into_words():
    assert clean_for_speech("a → b — c") == "a to b, c"


@pytest.mark.parametrize(
    "text, spoken",
    [
        # A bare `_` and `*` strip read these as one run-together word.
        ("Run set_app_name now", "Run set_app_name now"),
        ("Edit src/zrb/util/cli/style.py", "Edit src/zrb/util/cli/style.py"),
        ("Set ZRB_HOOKS_ENABLED off", "Set ZRB_HOOKS_ENABLED off"),
        ("See __init__.py", "See __init__.py"),
        # Markdown emphasis is still emphasis.
        ("**Done** and *later*", "Done and later"),
        ("_optional_ and __strong__", "optional and __strong__"),
        ("~~dropped~~", "dropped"),
        # Arithmetic is not emphasis.
        ("2 * 3 = 6", "2 * 3 = 6"),
        ("a*b*c", "a*b*c"),
    ],
)
def test_identifiers_survive_but_emphasis_does_not(text, spoken):
    assert clean_for_speech(text) == spoken


@pytest.mark.parametrize(
    "text, spoken",
    [
        ("~~~\ncode here\n~~~ after", "after"),
        ("Run this:\n```python\nx = 1", "Run this:"),
        ("See <https://x.com/a>. And more", "See. And more"),
        ("Go to https://x.com/a. Then", "Go to. Then"),
        ("Is it?\n\nYes.", "Is it? Yes."),
        ("Wrap it in ``` fences, then go on.", "Wrap it in fences, then go on."),
        ("Wiki: https://en.wikipedia.org/wiki/Foo_(bar) is nice.", "Wiki: is nice."),
        ("a ~~~ b", "a b"),
        ("One\n\nTwo", "One. Two"),
    ],
)
def test_clean_handles_every_fence_link_and_paragraph_form(text, spoken):
    assert clean_for_speech(text) == spoken


def test_fill_template_replaces_only_the_names_given():
    template = "I need to {action}{target}. {not_a_name} stays; so does {}."
    filled = fill_template(template, action="edit a file", target=" a.py")
    assert filled == "I need to edit a file a.py. {not_a_name} stays; so does {}."


def test_fill_template_fills_each_name_once():
    """A value that holds a placeholder is not filled in again."""
    filled = fill_template("{style}: {text}", style="say {text} warmly", text="hi")

    assert filled == "say {text} warmly: hi"
