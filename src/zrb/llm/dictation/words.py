"""Reading intent out of a transcript: wake words and yes/no answers."""

from __future__ import annotations

import difflib
import re
from collections.abc import Collection

from zrb.config.config import CFG

_WORD_RE = re.compile(r"[\w']+")
_STRIPPED_AFTER_WAKE_WORD = " ,.!?;:，。"
# How alike two words must be (difflib ratio) for a misheard one to match.
_NEAR_WORD = 0.75


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


def is_finished_phrase(
    text: str, trailing_words: Collection[str] | None = None
) -> bool:
    """Whether *text* could be a whole request: it has words and does not
    trail off on one a sentence rarely ends with ("and", "the", "um").
    *trailing_words* default to `CFG.LLM_DICTATION_TRAILING_WORDS`."""
    if trailing_words is None:
        trailing_words = CFG.LLM_DICTATION_TRAILING_WORDS
    words = _WORD_RE.findall(text.lower())
    return bool(words) and words[-1] not in {w.lower() for w in trailing_words}


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


def is_said_back(heard: str, said: str, min_share: float) -> bool:
    """Whether *heard* is mostly words of *said*: at least *min_share* of
    its words are, each spelled the same or nearly ("sleep" for "Sleep",
    "meen" for "mean", as a transcriber mishears zrb's own voice). Nothing
    heard, nothing said, or a *min_share* of 0 is never said back."""
    heard_words = _WORD_RE.findall(heard.lower())
    said_words = set(_WORD_RE.findall(said.lower()))
    if not heard_words or not said_words or min_share <= 0:
        return False
    matched = sum(1 for word in heard_words if _is_near_any(word, said_words))
    return matched / len(heard_words) >= min_share


def _is_near_any(word: str, words: set[str]) -> bool:
    if word in words:
        return True
    return bool(difflib.get_close_matches(word, words, n=1, cutoff=_NEAR_WORD))


def is_said_alone(
    text: str, phrases: list[list[str]], polite_words: Collection[str] | None = None
) -> bool:
    """Whether *text* is made only of *phrases* and *polite_words* (default:
    `CFG.LLM_DICTATION_POLITE_WORDS`), at least one phrase among them:
    "Stop!", "stop please"."""
    if polite_words is None:
        polite_words = CFG.LLM_DICTATION_POLITE_WORDS
    heard = [word.lower() for word in _WORD_RE.findall(text)]
    return _is_made_of(heard, phrases, {word.lower() for word in polite_words})


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
