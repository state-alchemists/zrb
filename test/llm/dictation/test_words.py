import pytest

from zrb.llm.dictation.words import split_phrases, strip_wake_word, to_answer

APPROVE = split_phrases(["yes", "go ahead", "ok"])
DENY = split_phrases(["no", "don't"])


def test_split_phrases_lowercases_and_drops_empty_ones():
    assert split_phrases(["Hey Jarvis", " ", "hi"]) == [["hey", "jarvis"], ["hi"]]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hey, Jarvis. Open it", "Open it"),
        ("hey jarvis", ""),
        ("hi there", "there"),
        ("jarvis hey", None),
    ],
)
def test_strip_wake_word(text, expected):
    wake_words = split_phrases(["hey jarvis", "hi"])
    assert strip_wake_word(text, wake_words) == expected


def test_without_wake_words_everything_counts():
    assert strip_wake_word("anything at all", []) == "anything at all"


@pytest.mark.parametrize(
    "said, answer",
    [
        ("Yes.", "yes"),
        ("yes please", "yes"),
        ("Go ahead!", "yes"),
        ("No.", "no"),
        ("Don't.", "no"),
        # A reason survives: the approval reads it as a denial with a message.
        ("No, use pytest", "No, use pytest"),
        # Not clearly a yes, so never an approval.
        (
            "yes but first rename the file to foo",
            "yes but first rename the file to foo",
        ),
        ("open the file", "open the file"),
    ],
)
def test_to_answer(said, answer):
    assert to_answer(said, APPROVE, DENY) == answer
