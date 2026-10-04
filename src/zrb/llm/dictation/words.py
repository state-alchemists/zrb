"""Reading intent out of a transcript: wake words and yes/no answers."""

from __future__ import annotations

import re
from collections.abc import Collection

from zrb.config.config import CFG

_WORD_RE = re.compile(r"[\w']+")
_STRIPPED_AFTER_WAKE_WORD = " ,.!?;:，。"
# What Whisper-like transcribers write for silence or noise. Lowercase, with
# end punctuation left off.
_NOISE_GUESSES = frozenset(
    {
        "thank you",
        "thanks for watching",
        "thank you for watching",
        "please subscribe",
        "subscribe to my channel",
        "like and subscribe",
        "the end",
        "you",
        "bye",
        "amara.org",
        "subtitles by the amara.org community",
    }
)


def split_phrases(phrases: list[str]) -> list[list[str]]:
    """Each phrase as lowercase words: ["hey jarvis"] -> [["hey", "jarvis"]]."""
    split = (_WORD_RE.findall(phrase.lower()) for phrase in phrases)
    return [words for words in split if words]


def strip_wake_word(text: str, wake_words: list[list[str]]) -> str | None:
    """*text* after its wake word, or ``None`` when it starts with none.

    Compared word by word, so "Hey, Jarvis." matches "hey jarvis". With no
    wake words, *text* is returned unchanged.
    """
    if not wake_words:
        return text
    words = list(_WORD_RE.finditer(text))
    heard = [word.group().lower() for word in words]
    for wanted in wake_words:
        if heard[: len(wanted)] == wanted:
            return text[words[len(wanted) - 1].end() :].lstrip(
                _STRIPPED_AFTER_WAKE_WORD
            )
    return None


def to_answer(
    text: str,
    approve_words: list[list[str]],
    deny_words: list[list[str]],
    polite_words: Collection[str] | None = None,
) -> str:
    """``yes`` for a transcript made only of approve phrases and polite words
    ("Yes.", "yes please", "okay, go ahead"), ``no`` for one made only of deny
    phrases and polite words ("No.", "no thanks"), else *text* unchanged.

    A tool approval reads ``yes`` as approve and anything else as a denial
    with that text as the reason, so a transcript that is not clearly a yes
    ("yes, but wait", "okay, no", "do it later") never approves, and
    "no, use pytest" keeps its reason. *polite_words* default to
    `CFG.LLM_DICTATION_POLITE_WORDS`.
    """
    if polite_words is None:
        polite_words = CFG.LLM_DICTATION_POLITE_WORDS
    polite = {word.lower() for word in polite_words}
    heard = [word.lower() for word in _WORD_RE.findall(text)]
    if _is_made_of(heard, approve_words, polite):
        return "yes"
    if _is_made_of(heard, deny_words, polite):
        return "no"
    return text


def count_words(text: str) -> int:
    """How many words *text* has."""
    return len(_WORD_RE.findall(text))


def is_transcriber_guess(text: str) -> bool:
    """Whether *text* is what a transcriber writes for noise, not speech: a
    phrase Whisper-like models produce for silence ("Thank you for
    watching."), or one phrase over and over ("and this and this", "you
    you you")."""
    words = [word.lower() for word in _WORD_RE.findall(text)]
    if not words:
        return False
    if " ".join(words) in _NOISE_GUESSES:
        return True
    return _is_one_phrase_repeated(words)


def _is_one_phrase_repeated(words: list[str]) -> bool:
    """Whether *words* are one phrase said at least twice, perhaps cut off
    part-way through the last time ("the top of the top of the top")."""
    for size in range(1, len(words) // 2 + 1):
        times = len(words) // size + 1
        if words == (words[:size] * times)[: len(words)]:
            return True
    return False


def is_said_alone(text: str, phrases: list[list[str]]) -> bool:
    """Whether *text* is made only of *phrases*, at least one of them:
    "Stop!", "stop". A polite word carries a yes or a no, not a stop: a stop
    is taken as one only when it is said alone."""
    heard = [word.lower() for word in _WORD_RE.findall(text)]
    return _is_made_of(heard, phrases, frozenset())


def _is_made_of(
    heard: list[str], phrases: list[list[str]], polite: Collection[str]
) -> bool:
    """Whether *heard* is one or more *phrases*, polite words between them
    allowed."""
    if not heard or not phrases:
        return False
    # reachable[i]: heard[:i] splits into phrases and polite words.
    reachable = [True] + [False] * len(heard)
    has_phrase = [False] * (len(heard) + 1)
    for start in range(len(heard)):
        if not reachable[start]:
            continue
        if heard[start] in polite:
            reachable[start + 1] = True
            has_phrase[start + 1] |= has_phrase[start]
        for phrase in phrases:
            end = start + len(phrase)
            if heard[start:end] == phrase:
                reachable[end] = True
                has_phrase[end] = True
    return reachable[-1] and has_phrase[-1]
