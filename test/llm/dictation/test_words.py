import pytest

from zrb.config.config import CFG
from zrb.llm.dictation.words import (
    count_words,
    is_finished_phrase,
    is_said_alone,
    is_said_back,
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


@pytest.mark.parametrize(
    "text, is_finished",
    [
        ("run the tests", True),
        ("run the tests and", False),
        ("open the", False),
        ("um", False),
        ("", False),
        ("Yes.", True),
    ],
)
def test_is_finished_phrase(text, is_finished):
    assert is_finished_phrase(text) is is_finished


def test_to_answer_takes_the_polite_words_it_is_given():
    assert to_answer("yes tolong", APPROVE, DENY, ["tolong"]) == "yes"
    assert to_answer("yes please", APPROVE, DENY, ["tolong"]) == "yes please"


def test_to_answer_reads_the_polite_words_from_cfg_when_called(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_DICTATION_POLITE_WORDS", ["mohon"])
    assert to_answer("no mohon", APPROVE, DENY) == "no"
    assert to_answer("no thanks", APPROVE, DENY) == "no thanks"


def test_is_finished_phrase_takes_the_trailing_words_it_is_given():
    assert not is_finished_phrase("saya mau dan", ["dan"])
    assert is_finished_phrase("open the", ["dan"])


def test_is_finished_phrase_reads_the_trailing_words_from_cfg(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_DICTATION_TRAILING_WORDS", ["yang"])
    assert not is_finished_phrase("buka file yang")
    assert is_finished_phrase("open the")


def test_is_said_alone_needs_one_of_the_phrases():
    stop = split_phrases(["stop", "hold on"])
    assert is_said_alone("Hold on, please.", stop)
    assert not is_said_alone("no", stop)
    assert not is_said_alone("please", stop)


@pytest.mark.parametrize(
    "heard, said",
    [
        # Taken from a session where zrb answered its own voice.
        ("sleep", "Goodnight. Sleep well."),
        ("well", "Rest well. I'm here when you need me."),
        ("did you mean", 'Did you mean "stop," "speak," or something else?'),
        ("Which one?", 'Which one — "stop" or "speak"?'),
        ("did you meen", "Did you mean stop or speak?"),  # misheard
    ],
)
def test_is_said_back_spots_zrbs_own_words(heard, said):
    assert is_said_back(heard, said, 0.8)


@pytest.mark.parametrize(
    "heard, said, min_share",
    [
        ("what time is it", "Did you mean stop or speak?", 0.8),
        ("use pytest instead of unittest", "Running the tests now.", 0.8),
        ("sleep", "", 0.8),  # zrb said nothing
        ("", "Sleep well.", 0.8),
        ("sleep", "Sleep well.", 0),  # switched off
    ],
)
def test_is_said_back_leaves_the_users_own_words(heard, said, min_share):
    assert not is_said_back(heard, said, min_share)


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


def test_is_said_back_reads_a_longer_transcript_letter_by_letter():
    """Misheard past the word match: still zrb's sentence, near enough."""
    said = "so blue comes at you from every direction and the sky looks blue"
    assert is_said_back("from every directions and the skies", said, 0.8)
