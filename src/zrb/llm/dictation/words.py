"""Reading intent out of a transcript: wake words and yes/no answers."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[\w']+")
_STRIPPED_AFTER_WAKE_WORD = " ,.!?;:，。"
# Words an approval may add after its approve phrase, as in "yes please";
# a longer answer is sent as said.
_ANSWER_EXTRA_WORDS = 3


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
    text: str, approve_words: list[list[str]], deny_words: list[list[str]]
) -> str:
    """``yes`` for a short transcript opening with an approve phrase ("Yes.",
    "yes please"), ``no`` for a deny phrase said alone ("No."), else *text*
    unchanged.

    A tool approval reads ``yes`` as approve and anything else as a denial
    with that text as the reason, so a transcript that is not clearly a yes
    never approves, and "no, use pytest" keeps its reason.
    """
    heard = [word.lower() for word in _WORD_RE.findall(text)]
    for phrase in approve_words:
        fits = len(heard) <= len(phrase) + _ANSWER_EXTRA_WORDS
        if fits and heard[: len(phrase)] == phrase:
            return "yes"
    if heard in deny_words:
        return "no"
    return text
