"""Reading intent out of a transcript: wake words and yes/no answers."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[\w']+")
_STRIPPED_AFTER_WAKE_WORD = " ,.!?;:，。"
# Words a yes or a no may carry without changing it, as in "yes please".
_POLITE_WORDS = frozenset({"please", "thanks", "thank", "you"})


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
    """``yes`` for a transcript made only of approve phrases and polite words
    ("Yes.", "yes please", "okay, go ahead"), ``no`` for one made only of deny
    phrases and polite words ("No.", "no thanks"), else *text* unchanged.

    A tool approval reads ``yes`` as approve and anything else as a denial
    with that text as the reason, so a transcript that is not clearly a yes
    ("yes, but wait", "okay, no", "do it later") never approves, and
    "no, use pytest" keeps its reason.
    """
    heard = [word.lower() for word in _WORD_RE.findall(text)]
    if _is_made_of(heard, approve_words):
        return "yes"
    if _is_made_of(heard, deny_words):
        return "no"
    return text


def _is_made_of(heard: list[str], phrases: list[list[str]]) -> bool:
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
        if heard[start] in _POLITE_WORDS:
            reachable[start + 1] = True
            has_phrase[start + 1] |= has_phrase[start]
        for phrase in phrases:
            end = start + len(phrase)
            if heard[start:end] == phrase:
                reachable[end] = True
                has_phrase[end] = True
    return reachable[-1] and has_phrase[-1]
