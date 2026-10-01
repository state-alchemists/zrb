import pytest

from zrb.llm.speech.text import clean_for_speech, fill_template, fit_for_speech

NOTE = "The full answer is on screen."


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


def test_a_short_reply_is_spoken_in_full():
    assert fit_for_speech("Short.", 30, NOTE) == "Short."
    assert fit_for_speech("x" * 1000, 0, NOTE) == "x" * 1000


@pytest.mark.parametrize(
    "text, max_chars, opening",
    [
        # The last sentence end in the second half of the window.
        (
            "First one here. Second sentence. Third runs long past it.",
            40,
            "First one here. Second sentence.",
        ),
        # A dot inside a word, as in "main.py", is not a sentence end.
        (
            "Use main.py now and then keep going for a long time",
            30,
            "Use main.py now and then keep.",
        ),
        # No sentence end: the last clause break.
        ("alpha beta gamma, delta epsilon zeta eta theta", 30, "alpha beta gamma."),
        # No break at all: the last whole word, never half of one.
        ("alphabetagammadelta epsilonzetaetatheta iota", 30, "alphabetagammadelta."),
    ],
)
def test_a_long_reply_is_cut_at_a_boundary_and_says_so(text, max_chars, opening):
    assert fit_for_speech(text, max_chars, NOTE) == f"{opening} {NOTE}"


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


def test_an_empty_note_adds_nothing():
    assert fit_for_speech("one two three four five six", 10, "") == "one two."


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


@pytest.mark.parametrize(
    "text, max_chars, opening",
    [
        # The end of the window is not the end of a sentence.
        (
            "Open the config file main.py and change it now please.",
            26,
            "Open the config file.",
        ),
        # Nor is the dot after a lone letter.
        (
            "Use a tool, e.g. grep here, to find it. Then more words follow.",
            22,
            "Use a tool, e.g. grep.",
        ),
    ],
)
def test_a_cut_never_ends_on_a_false_sentence_end(text, max_chars, opening):
    assert fit_for_speech(text, max_chars, "N") == f"{opening} N"


def test_a_cut_may_end_after_a_one_letter_word():
    text = "Should we go on? I. " + "More words follow here. " * 3
    assert fit_for_speech(text, 30, "NOTE") == "Should we go on? I. NOTE"


def test_fill_template_replaces_only_the_names_given():
    template = "I need to {action}{target}. {not_a_name} stays; so does {}."
    filled = fill_template(template, action="edit a file", target=" a.py")
    assert filled == "I need to edit a file a.py. {not_a_name} stays; so does {}."
