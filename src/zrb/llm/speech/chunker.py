"""Cutting a reply into speakable sentences while it is still streaming.

`SpeechChunker` takes the reply's text deltas as they arrive and hands back
each run of whole sentences as soon as it is complete, cleaned for speech, so
the first sentence can be spoken while the model is still writing the rest.

Block markup is decided a line at a time: a code fence and everything inside
it, and table rows, are never spoken. A line is held back only while its
first characters could still open one of those (a backtick, a tilde, a pipe);
any other line is prose from its first character, so a sentence is spoken
without waiting for its line to end.
"""

from __future__ import annotations

import re

from zrb.llm.speech.text import clean_for_speech

# A sentence end: punctuation followed by space, so "main.py" and "e.g." do
# not end one but "I." does. A blank line ends one too.
_BOUNDARY_RE = re.compile(r"(?<!\.[a-zA-Z])[.!?](?=\s)|\n[ \t]*\n")
_CLAUSE_END_RE = re.compile(r"[,;:](?=\s)")
_FENCE_MARKERS = ("```", "~~~")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
# Characters that may open a fence or a table row, so a line starting with
# one waits until it can be told apart from prose.
_AMBIGUOUS_STARTS = "`~|"


class SpeechChunker:
    """Turns streamed markdown into cleaned chunks of whole sentences.

    A chunk is emitted at the first sentence end or blank line once it holds
    at least *min_chars* of speech, so a lone "OK." waits for the next
    sentence instead of becoming a clip of its own. Prose running past
    *max_chars* with no sentence end is cut at its last clause break, else its
    last space.
    """

    def __init__(self, min_chars: int = 20, max_chars: int = 250) -> None:
        self._min_chars = max(min_chars, 0)
        self._max_chars = max(max_chars, self._min_chars + 1)
        self.reset()

    def reset(self) -> None:
        """Forget everything fed so far."""
        self._prose = ""  # accepted prose not yet emitted
        self._line = ""  # the current, unfinished line
        self._line_taken = 0  # how much of `_line` is already in `_prose`
        self._in_fence = False

    def feed(self, delta: str) -> list[str]:
        """Take *delta*, returning every chunk it completed."""
        self._line += delta
        chunks: list[str] = []
        while "\n" in self._line:
            line, self._line = self._line.split("\n", 1)
            taken, self._line_taken = self._line_taken, 0
            if not taken and line.strip().startswith(_FENCE_MARKERS):
                # A fence opening or closing ends the prose before it.
                self._in_fence = not self._in_fence
                chunks += self._drain(force=True)
            else:
                self._take_line(line, taken)
        self._take_partial_line()
        return chunks + self._drain(force=False)

    def flush(self) -> list[str]:
        """Every chunk still held, however short: the reply, or the text
        before a tool call, has ended."""
        line, taken = self._line, self._line_taken
        is_fence = line.strip().startswith(_FENCE_MARKERS)
        if not self._in_fence and (taken or not is_fence and self._is_prose_line(line)):
            self._prose += line[taken:]
        self._line, self._line_taken = "", 0
        self._in_fence = False
        return self._drain(force=True)

    def _take_line(self, line: str, taken: int) -> None:
        """File a finished *line*, of which *taken* characters are already
        prose."""
        if self._in_fence or not taken and not self._is_prose_line(line):
            return
        self._prose += line[taken:] + "\n"

    def _take_partial_line(self) -> None:
        if self._in_fence or self._is_ambiguous(self._line):
            return
        self._prose += self._line[self._line_taken :]
        self._line_taken = len(self._line)

    def _is_ambiguous(self, line: str) -> bool:
        """Whether *line* might still turn out to be a fence or a table row."""
        if self._line_taken:
            return False
        stripped = line.lstrip()
        if not stripped:
            return True
        if stripped[0] not in _AMBIGUOUS_STARTS:
            return False
        if stripped[0] == "|":
            return True
        # Up to three characters, a backtick or tilde may be opening a fence.
        return len(stripped) < 3 or stripped.startswith(_FENCE_MARKERS)

    def _is_prose_line(self, line: str) -> bool:
        return not (_TABLE_ROW_RE.match(line) or _TABLE_SEPARATOR_RE.match(line))

    def _drain(self, force: bool) -> list[str]:
        chunks: list[str] = []
        while True:
            end = self._find_cut()
            if end is None:
                break
            chunk = clean_for_speech(self._prose[:end])
            self._prose = self._prose[end:]
            if chunk:
                chunks.append(chunk)
        if force:
            rest = clean_for_speech(self._prose)
            self._prose = ""
            if rest:
                chunks.append(rest)
        return chunks

    def _find_cut(self) -> int | None:
        """Where the next chunk ends in `_prose`, if one is complete."""
        for match in _BOUNDARY_RE.finditer(self._prose):
            if len(clean_for_speech(self._prose[: match.end()])) >= self._min_chars:
                return match.end()
        if len(self._prose) <= self._max_chars:
            return None
        window = self._prose[: self._max_chars]
        clause_ends = [m.end() for m in _CLAUSE_END_RE.finditer(window)]
        if clause_ends:
            return clause_ends[-1]
        space = window.rfind(" ")
        return space + 1 if space > 0 else self._max_chars
