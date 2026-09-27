import pytest

from zrb.llm.speech.text import clean_for_speech, fit_for_speech

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
