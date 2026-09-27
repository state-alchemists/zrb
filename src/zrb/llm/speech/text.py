"""Turning a markdown reply into text worth reading aloud."""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"(```|~~~).*?\1", re.DOTALL)
# A fence opening a line with no close runs to the end: a reply cut mid-code.
_UNCLOSED_FENCE_RE = re.compile(r"^[ \t]*(```|~~~).*\Z", re.DOTALL | re.MULTILINE)
_STRAY_MARKER_RE = re.compile(r"`+|~{3,}")
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
# A table's separator row, with or without outer pipes: `--- | :---:`.
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
# Balanced parentheses belong to the URL; trailing punctuation to the sentence.
_URL_RE = re.compile(r"<?https?://(?:[^\s<>()]|\([^\s<>()]*\))+(?<![.,;:!?])>?")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_QUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_RULE_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
# Emphasis markers, matched as pairs and never inside a word, so
# `set_app_name` and `2 * 3` survive. `__strong__` is left alone on purpose:
# it is indistinguishable from the dunder in `__init__.py`.
_EMPHASIS_RES = (
    re.compile(r"(?<!\*)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\*)", re.DOTALL),
    re.compile(r"(?<!~)~~(?=\S)(.+?)(?<=\S)~~(?!~)", re.DOTALL),
    re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=\S)\*(?![\w*])"),
    re.compile(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=\S)_(?![\w_])", re.DOTALL),
)
# espeak-ng reads some emoji aloud ("smiling face").
_NON_SPEECH_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]"
)
# A sentence ends at punctuation followed by space, so the dot in "main.py"
# does not count, nor one after a lone letter ("e.g.").
_SENTENCE_END_RE = re.compile(r"(?<!\b[a-zA-Z])[.!?](?=\s)")
_CLAUSE_END_RE = re.compile(r"[,;:](?=\s)")


def clean_for_speech(text: str) -> str:
    """Reduce markdown to speakable prose: no code, tables, URLs or markup.

    Fences go before inline code, and links before bare URLs, or the triple
    backticks and link labels are mangled.
    """
    text = _FENCE_RE.sub(" ", text)
    text = _UNCLOSED_FENCE_RE.sub(" ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _URL_RE.sub(" ", text)
    text = _strip_tables(text)
    text = _TABLE_ROW_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _STRAY_MARKER_RE.sub("", text)
    text = _RULE_RE.sub("", text)
    text = _HEADING_RE.sub("", text)
    text = _QUOTE_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    for emphasis in _EMPHASIS_RES:
        text = emphasis.sub(r"\1", text)
    text = _NON_SPEECH_RE.sub("", text)
    text = text.replace("→", " to ").replace("—", ", ").replace("–", ", ")
    # Paragraph breaks become sentence pauses.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"([.!?:;,]?) ?\n\s*\n+", lambda m: (m.group(1) or ".") + "\n", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip()


def _strip_tables(text: str) -> str:
    """Drop every table: its header, separator and pipe-separated rows."""
    kept: list[str] = []
    in_table = False
    for line in text.split("\n"):
        if _TABLE_SEPARATOR_RE.match(line):
            if kept and "|" in kept[-1]:
                kept.pop()  # the header row
            in_table = True
            continue
        if in_table and "|" in line:
            continue
        in_table = False
        kept.append(line)
    return "\n".join(kept)


def fit_for_speech(text: str, max_chars: int, note: str) -> str:
    """*text* if it fits in *max_chars* (0: no limit), else its opening
    followed by *note*.

    The opening ends at the last sentence end in the second half of the
    window, else the last clause break there, else the last word, so speech
    never stops mid-word.
    """
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return f"{_cut(text, max_chars)} {note}".strip()


def _cut(text: str, max_chars: int) -> str:
    window = text[:max_chars]
    half = max_chars / 2
    # One character past the window, so the lookahead sees what follows it.
    sentence_ends = [
        m.end()
        for m in _SENTENCE_END_RE.finditer(text[: max_chars + 1])
        if m.end() >= half
    ]
    if sentence_ends:
        return window[: sentence_ends[-1]]
    clause_ends = [
        m.start() for m in _CLAUSE_END_RE.finditer(window) if m.start() >= half
    ]
    if clause_ends:
        return window[: clause_ends[-1]] + "."
    ends_mid_word = not text[max_chars : max_chars + 1].isspace()
    if ends_mid_word and " " in window:
        window = window[: window.rfind(" ")]
    return window.rstrip(" ,;:") + "."
