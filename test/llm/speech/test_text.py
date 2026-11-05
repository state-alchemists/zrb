import pytest

from zrb.llm.speech.text import (
    WHOLE_READ_OK_CHARS,
    clean_for_speech,
    fill_template,
    needs_spoken_block,
    without_blockquotes,
)


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


def test_a_quote_is_left_out_of_what_is_read_aloud():
    """A quote in a reply is typography: shown set off, never said. A reply that
    opens no block is read whole except for the paragraphs it quoted."""
    reply = "Here is the line:\n\n> the whole world is a stage\n\nand that is it."

    assert without_blockquotes(reply) == "Here is the line:\n\n\nand that is it."
    assert "stage" not in clean_for_speech(without_blockquotes(reply))
    assert "the whole world is a stage" in clean_for_speech(reply)


def test_a_quote_takes_its_lazy_continuation_lines_with_it():
    """A quoted paragraph keeps the lines under it that carry no `>`, so removing
    only the marked line would leave half of the quote in the ear."""
    reply = (
        "The excerpt is:\n\n> first line of the quote\nand its continuation.\n\nDone."
    )

    spoken = clean_for_speech(without_blockquotes(reply))

    assert "continuation" not in spoken
    assert "The excerpt is" in spoken and "Done" in spoken


def test_a_line_that_begins_a_block_ends_the_quote():
    reply = "> quoted\n- item one\n> quoted again"

    assert without_blockquotes(reply) == "- item one"


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


def test_a_short_reply_needs_no_block():
    """The rule already says a short answer needs none, so the check must not
    quarrel with the rule it exists to enforce."""
    assert not needs_spoken_block("Fixed the parser. The tests pass.")


def test_a_reply_that_opens_a_block_asks_for_nothing_more():
    """Even an empty one, and even when the reply around it is long: the model
    has said what the ear gets."""
    assert not needs_spoken_block("<spoken></spoken>\n" + "Shown only. " * 60)
    assert not needs_spoken_block("<spoken>Done.</spoken>\n" + "Shown only. " * 60)


def test_a_reply_full_of_quoted_text_is_measured_by_what_is_said():
    """A quote is shown and never said, so a long one must not make the reply
    look too long to listen to when the listener hears one line."""
    reply = "> " + "a quoted log line, shown and never read out " * 20 + "\n\nDone."

    assert len(reply) > WHOLE_READ_OK_CHARS + 400
    assert not needs_spoken_block(reply)


def test_a_reply_holding_a_table_needs_a_block():
    """The cleaning drops the table, so the ear hears the sentence pointing at
    it and none of its numbers."""
    reply = (
        "Where things stand:\n\n"
        "| item | cost |\n"
        "| --- | ---: |\n"
        "| warning | an hour |"
    )

    assert needs_spoken_block(reply)


def test_a_reply_holding_a_fenced_block_needs_a_block():
    assert needs_spoken_block("Run this:\n\n```bash\nmake test\n```")


def test_a_reply_long_enough_to_be_a_lecture_needs_a_block():
    sentence = "A sentence of no consequence. "

    assert not needs_spoken_block(sentence * 5)
    assert needs_spoken_block(sentence * 20)
