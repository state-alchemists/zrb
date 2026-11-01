"""The `<spoken>` block: the part of a reply read aloud, and the part only shown.

A reply may mark what belongs to the ear:

    <spoken>😊 Fixed the parser. The tests pass.</spoken>

Inside the block is spoken, after `clean_for_speech`; everything outside it is
shown on screen and never spoken. The markers themselves reach neither. A reply
with no block is spoken whole, so a model that forgets the block degrades to
that instead of falling silent.

On screen the block is set off as a markdown blockquote, so a reader sees at a
glance which part of the reply is also being read aloud — the markers are gone,
and without the quote the spoken sentences would look like just more prose. A
quote the reply writes for itself is the other way round: typography, shown and
never said, because only a block reaches the ear.

That quote belongs to the durable copy, the one `shown_text` renders once the
turn ends. The copy a reply streams into while it is still being written stays
raw, on purpose: it is an echo that folds into a placeholder when the run ends,
because `BaseUI.stream_ai_response` appends the answer itself, and quoting an
echo would make the text reflow into quotes as it arrives for a copy nobody
keeps. `SpokenSplitter` therefore holds no quoting state; only `shown_text` does.

`split_spoken` cuts a whole reply; `SpokenSplitter` cuts one while it streams.
They share the rules below, so the two copies of a reply cannot disagree: a
block is opened by `<spoken>` and closed by the next `</spoken>`, markers do not
nest, an unclosed block runs to the end, and several blocks are read in order.
A marker is always taken out of the screen copy — a stray `</spoken>` included,
which opens nothing and leaves the whole reply spoken. A tag written inside an
inline code span or a fenced block is the tag being quoted, not used: it opens
nothing, and both copies leave it where the reply put it.
"""

from __future__ import annotations

from collections.abc import Iterator

OPEN_TAG = "<spoken>"
CLOSE_TAG = "</spoken>"
_TAGS = (OPEN_TAG, CLOSE_TAG)
# What a screen puts in front of each line of a block: markdown's own quote.
QUOTE_MARKER = "> "
# The longest tag less its last character: a delta can end anywhere inside one.
_LONGEST_PARTIAL_TAG = max(len(tag) for tag in _TAGS) - 1
# How many backticks or tildes open a fenced block; one or two are inline code.
_FENCE_MIN = 3


def partial_marker(text: str) -> str:
    """The tail of *text* that could still turn out to be a marker, so nothing
    is decided about it yet: `<spo` may become `<spoken>`. Empty when the text
    ends on anything else."""
    return _split_partial_tag(text)[1]


def shown_text(text: str) -> str:
    """*text* as a screen shows it: everything except the markers, which belong
    to the ear alone, with each block set off as a markdown blockquote so the
    part that is read aloud stands apart from the rest. A reply that marks
    nothing comes back unchanged."""
    if OPEN_TAG not in text and CLOSE_TAG not in text:
        return text
    return _quote_blocks(text)


def split_spoken(text: str) -> tuple[str | None, str]:
    """``(spoken, shown)`` for the whole *text*.

    *spoken* is ``None`` when the reply opens no block at all: the whole reply
    is meant for the ear then. An empty block reads as ``""`` instead — the
    model said nothing is to be read aloud, which is not the same thing as
    saying nothing about it.

    The whole reply is in hand, so prose in front of the first block is known to
    be for the eye alone and stays unspoken; a stream cannot know that
    (`SpokenSplitter`).
    """
    splitter = SpokenSplitter()
    is_spoken = _is_spoken_reply(text)
    if is_spoken:
        splitter.speak_only_blocks()
    shown, spoken = splitter.feed(text)
    rest_shown, rest_spoken = splitter.flush()
    shown, spoken = shown + rest_shown, spoken + rest_spoken
    if not is_spoken:
        return None, shown
    return spoken, shown


class SpokenSplitter:
    """One reply's text, taken in the pieces it arrives in.

    `feed` takes the next piece and returns ``(shown, spoken)``: what a screen
    shows and what a voice reads. Both hold back whatever could still turn into
    a marker — a piece can end in `<spo`, which the next piece may complete — so
    a tag split across two deltas is never shown or said as text. `flush` gives
    those characters up when the reply ends there, or when the block being
    spoken does.

    A stream speaks the prose outside a block until one opens: what it has
    already said cannot be taken back, and a reply that keeps no block must be
    read whole. `speak_only_blocks` drops that, for a caller holding the whole
    reply, which knows whether a block is coming.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Forget what was read: the next reply starts inside no block, and
        speaks them all until one opens."""
        self._is_spoken = False
        self._speaks_outside = True
        self._has_spoken = False
        self._has_block = False
        self._scanner = _MarkerScanner()
        self._held = ""

    @property
    def has_block(self) -> bool:
        """Whether a `<spoken>` block has opened in this reply so far.

        A stream cannot unsay what it has already said, so a caller that would
        rather not guess holds its first sentence until this turns true — or
        until a second sentence proves no block is coming.
        """
        return self._has_block

    def speak_only_blocks(self) -> None:
        """Say nothing outside a block, not even before the first one opens."""
        self._speaks_outside = False

    def feed(self, text: str) -> tuple[str, str]:
        """``(shown, spoken)`` for *text*, and for whatever the last call held."""
        pending, self._held = _split_partial_tag(self._held + text)
        shown, spoken = self._read(pending)
        return "".join(shown), "".join(spoken)

    def flush(self) -> tuple[str, str]:
        """``(shown, spoken)`` for what a possible marker held back: the reply
        ends here, so it was prose after all."""
        held, self._held = self._held, ""
        if not held:
            return "", ""
        return (held, held) if self._is_outside_spoken() else (held, "")

    def _is_outside_spoken(self) -> bool:
        """Whether text outside a block is said rather than only shown."""
        return self._is_spoken or self._speaks_outside

    def _read(self, text: str) -> tuple[list[str], list[str]]:
        """Walk *text*, filing each run of it as shown, and as spoken too while
        a block is open."""
        shown: list[str] = []
        spoken: list[str] = []
        cursor = 0
        while cursor < len(text):
            found = self._scanner.find(text, cursor)
            end = len(text) if found is None else found[0]
            piece = text[cursor:end]
            if piece:
                shown.append(piece)
                if self._is_outside_spoken():
                    spoken.append(piece)
                    self._has_spoken = True
            if found is None:
                break
            self._switch(text[found[0] : found[1]], spoken)
            cursor = found[1]
        return shown, spoken

    def _switch(self, tag: str, spoken: list[str]) -> None:
        """Enter or leave the block *tag* marks. Markers do not nest, so any
        `<spoken>` opens one and any `</spoken>` ends it; from the first block
        on, only blocks are said. Two blocks one after the other are two things
        to say, so a space is said between them."""
        opening = tag == OPEN_TAG
        if opening and not self._is_spoken and self._has_spoken:
            spoken.append(" ")
        self._is_spoken = opening
        if opening:
            self._speaks_outside = False
            self._has_block = True


def _next_tag(text: str, start: int) -> tuple[int, int] | None:
    """Where the first marker in *text* at or after *start* is: ``(begin, end)``,
    or ``None`` when the rest of *text* holds none."""
    found: tuple[int, int] | None = None
    for tag in _TAGS:
        index = text.find(tag, start)
        if index < 0:
            continue
        if found is None or index < found[0]:
            found = (index, index + len(tag))
    return found


def _marker_spans(text: str) -> Iterator[tuple[int, int]]:
    """Every marker in *text*, in order, as ``(begin, end)``."""
    scanner = _MarkerScanner()
    cursor = 0
    while True:
        found = scanner.find(text, cursor)
        if found is None:
            return
        yield found
        cursor = found[1]


def _is_spoken_reply(text: str) -> bool:
    """Whether *text* opens a block, as opposed to naming the tag in code."""
    scanner = _MarkerScanner()
    cursor = 0
    while True:
        found = scanner.find(text, cursor)
        if found is None:
            return False
        if text[found[0] : found[1]] == OPEN_TAG:
            return True
        cursor = found[1]


class _MarkerScanner:
    """Which tags in a reply are markers, and which are the tag being written
    about.

    A reply explaining the syntax writes `<spoken>` inside backticks or a fenced
    block, and that is content: read as a marker it opens a block that never
    closes, so the rest of the reply is shown as a quote and said aloud. The
    state that tells the two apart — the fence we are in, the backticks opened on
    the line so far — is kept across calls, so the whole-reply and streaming
    copies decide with one rule.

    Only the shapes a reply actually writes are recognized: a fenced block, and a
    same-line backtick span. An indented code block is not, no more than it is
    for `clean_for_speech`.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Start a reply: no fence open, no line begun."""
        self._fence_mark = ""
        self._fence_size = 0
        self._line = ""

    def find(self, text: str, start: int) -> tuple[int, int] | None:
        """The first marker in *text* at or after *start*, or ``None``.

        Everything read on the way is taken into the code state, so a tag that
        sits in code is passed over as content instead of being yielded.
        """
        cursor = start
        while True:
            found = _next_tag(text, cursor)
            if found is None:
                self._take(text[cursor:])
                return None
            self._take(text[cursor : found[0]])
            if not self._is_code():
                return found
            self._take(text[found[0] : found[1]])
            cursor = found[1]

    def _take(self, chunk: str) -> None:
        """Read *chunk* into the open line and the fence state, a finished line
        at a time; the last line is still open and may grow."""
        lines = (self._line + chunk).split("\n")
        self._line = lines.pop()
        for line in lines:
            self._close_line(line)

    def _close_line(self, line: str) -> None:
        """Let *line* decide the fence the next one starts in: an opening run of
        three or more, then a run at least as long with nothing after it."""
        mark, size = _leading_run(line)
        if not self._fence_mark:
            if size >= _FENCE_MIN:
                self._fence_mark, self._fence_size = mark, size
            return
        is_closer = (
            mark == self._fence_mark
            and size >= self._fence_size
            and not line.lstrip(" \t")[size:].strip()
        )
        if is_closer:
            self._fence_mark, self._fence_size = "", 0

    def _is_code(self) -> bool:
        """Whether a tag at the end of the open line is code: inside a fence, on
        the line that opens one, or between the backticks of a span."""
        if self._fence_mark:
            return True
        mark, size = _leading_run(self._line)
        if mark == "`" and size >= _FENCE_MIN:
            return True
        return _is_inside_span(self._line)


def _is_inside_span(line: str) -> bool:
    """Whether *line* ends inside an inline code span.

    A span is opened by a run of backticks and closed by the next run of the same
    length, so `` `a` `` and ``` ``a`b`` ``` both work: the delimiters are
    matched by size rather than counted, since a longer run is how a span holds a
    backtick of its own.
    """
    size = 0
    cursor = 0
    while True:
        start = line.find("`", cursor)
        if start < 0:
            return size != 0
        run = len(line) - start - len(line[start:].lstrip("`"))
        if size == 0:
            size = run
        elif run == size:
            size = 0
        cursor = start + run


def _leading_run(line: str) -> tuple[str, int]:
    """The fence candidate *line* opens with: the character and how many of it,
    counted from the first one that is not indentation."""
    stripped = line.lstrip(" \t")
    if not stripped or stripped[0] not in "`~":
        return "", 0
    mark = stripped[0]
    return mark, len(stripped) - len(stripped.lstrip(mark))



def _quote_blocks(text: str) -> str:
    """*text* with each block set off as a blockquote: the markers out, every
    line of the block marked, and a blank line where a quote would otherwise run
    into the prose beside it. A block that opens mid-sentence is moved onto a
    line of its own — a quote cannot start in the middle of one."""
    shown = ""
    cursor = 0
    is_spoken = False
    for begin, end in _marker_spans(text):
        body = text[cursor:begin]
        shown += _quoted(body) if is_spoken else body
        was_quoted = is_spoken and bool(body.strip())
        is_spoken = text[begin:end] == OPEN_TAG
        if is_spoken:
            shown += _quote_open_gap(text, begin, shown)
        elif was_quoted:
            shown += _quote_close_gap(text, end)
        cursor = end
    tail = text[cursor:]
    return shown + (_quoted(tail) if is_spoken else tail)


def _quote_open_gap(text: str, begin: int, shown: str) -> str:
    """What a quote needs in front of it so it does not open in the middle of a
    line: nothing when the reply already broke the line."""
    if not begin or text[begin - 1] == "\n" or shown.endswith("\n"):
        return ""
    return "\n"


def _quoted(body: str) -> str:
    """*body* as a blockquote, with the blank lines at either end left outside:
    they belong to the reply, not to what is being quoted."""
    body = body.strip("\n")
    if not body:
        return ""
    marked = [
        QUOTE_MARKER + line if line else QUOTE_MARKER.rstrip()
        for line in body.split("\n")
    ]
    return "\n".join(marked)


def _quote_close_gap(text: str, end: int) -> str:
    """What a quote needs after it so the prose that follows starts a paragraph
    of its own rather than a lazy continuation of the quote."""
    rest = text[end:]
    if not rest or rest.startswith("\n\n"):
        return ""
    return "\n" if rest.startswith("\n") else "\n\n"


def _split_partial_tag(text: str) -> tuple[str, str]:
    """*text* split before a tail that could still turn out to be a marker.
    Those characters settle nothing yet, so they are held back."""
    for size in range(min(len(text), _LONGEST_PARTIAL_TAG), 0, -1):
        tail = text[-size:]
        if any(len(tail) < len(tag) and tag.startswith(tail) for tag in _TAGS):
            return text[:-size], tail
    return text, ""
