import pytest

from zrb.config.config import CFG
from zrb.llm.dictation.words import (
    count_words,
    is_answer,
    is_said_alone,
    is_transcriber_guess,
    split_phrases,
    strip_wake_word,
    to_answer,
)

APPROVE = split_phrases(["yes", "yeah", "go ahead", "ok", "okay", "do it"])
DENY = split_phrases(["no", "don't", "stop"])


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
        ("okay, go ahead, thanks", "yes"),
        ("No thanks.", "no"),
        # A denial or a hedge anywhere keeps an answer from approving.
        ("Okay, no, stop.", "Okay, no, stop."),
        ("Yes, but don't.", "Yes, but don't."),
        ("yes wait no", "yes wait no"),
        ("Yeah no", "Yeah no"),
        ("ok run the tests", "ok run the tests"),
        ("do it later", "do it later"),
        ("please", "please"),
        ("", ""),
    ],
)
def test_to_answer(said, answer):
    assert to_answer(said, APPROVE, DENY) == answer


def test_to_answer_takes_the_polite_words_it_is_given():
    assert to_answer("yes tolong", APPROVE, DENY, ["tolong"]) == "yes"
    assert to_answer("yes please", APPROVE, DENY, ["tolong"]) == "yes please"


def test_to_answer_reads_the_polite_words_from_cfg_when_called(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_DICTATION_POLITE_WORDS", ["mohon"])
    assert to_answer("no mohon", APPROVE, DENY) == "no"
    assert to_answer("no thanks", APPROVE, DENY) == "no thanks"


def test_is_said_alone_needs_one_of_the_phrases():
    stop = split_phrases(["stop", "hold on"])
    assert is_said_alone("Hold on.", stop)
    # A polite word carries a yes or a no, not a stop: "please" is not a stop
    # word, so this is a message for the model, which reads it as one.
    assert not is_said_alone("Hold on, please.", stop)
    assert not is_said_alone("no", stop)
    assert not is_said_alone("please", stop)


@pytest.mark.parametrize(
    "said, answer",
    [
        ("Yes.", True),
        ("yes please", True),
        ("Go ahead!", True),
        ("No thanks.", True),
        ("Okay, go ahead, thanks", True),
        ("", False),
        ("open the file", False),
        ("do it later", False),
        ("run the tests", False),
    ],
)
def test_is_answer_reads_a_polite_yes_or_no_as_an_answer(said, answer):
    """Whether a transcript is an answer at all, not which one it is — the
    reading `_is_answer_or_stop` needs (PR #561 review)."""
    assert is_answer(said, APPROVE, DENY) == answer


def test_is_answer_asks_the_question_to_answer_answers_with():
    """Both read a transcript as a yes, a no, or neither, so a caller deciding
    only whether something is an answer (`_is_answer_or_stop`) cannot disagree
    with the approval that answer will carry. "Okay, no, stop" is neither: a
    hedge of both families at once is a message, and stays one."""
    assert not is_answer("Okay, no, stop.", APPROVE, DENY)
    assert to_answer("Okay, no, stop.", APPROVE, DENY) == "Okay, no, stop."


@pytest.mark.parametrize(
    "text",
    [
        "and this and this",
        "the top of the top of the top",  # cut off part-way, as reported
        "you you you",
        "Thank you.",
        "Thanks for watching!",
    ],
)
def test_is_transcriber_guess_spots_text_written_for_noise(text):
    assert is_transcriber_guess(text)


@pytest.mark.parametrize(
    "text", ["run the tests", "very very good", "what time is it", "yes", ""]
)
def test_is_transcriber_guess_leaves_speech(text):
    assert not is_transcriber_guess(text)


def test_count_words():
    assert count_words("Don't stop, please!") == 3
    assert count_words("") == 0
