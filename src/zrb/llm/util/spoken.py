"""The `<spoken>` block: the part of a reply read aloud, and the part only shown.

A reply may mark what belongs to the ear:

    <spoken>😊 Fixed the parser. The tests pass.</spoken>

Inside the block is spoken, after `clean_for_speech`; everything outside it is
shown on screen and never spoken. The markers themselves reach neither. A reply
with no block is spoken whole, exactly as before the block existed, so a model
that forgets it degrades to that behaviour instead of falling silent.

`split_spoken` cuts a whole reply; `SpokenSplitter` cuts one while it streams.
They share the rules below, so the two copies of a reply cannot disagree: a
block is opened by `<spoken>` and closed by the next `</spoken>`, markers do not
nest, an unclosed block runs to the end, and several blocks are read in order.
A marker is always taken out of the screen copy — a stray `</spoken>` included,
which opens nothing and leaves the whole reply spoken.
"""

from __future__ import annotations

OPEN_TAG = "<spoken>"
CLOSE_TAG = "</spoken>"
_TAGS = (OPEN_TAG, CLOSE_TAG)
# The longest tag less its last character: a delta can end anywhere inside one.
_LONGEST_PARTIAL_TAG = max(len(tag) for tag in _TAGS) - 1


def partial_marker(text: str) -> str:
    """The tail of *text* that could still turn out to be a marker, so nothing
    is decided about it yet: `<spo` may become `<spoken>`. Empty when the text
    ends on anything else."""
    return _split_partial_tag(text)[1]


def shown_text(text: str) -> str:
    """*text* as a screen shows it: everything except the markers, which belong
    to the ear alone. A reply with no block comes back unchanged."""
    return split_spoken(text)[1]


def split_spoken(text: str) -> tuple[str | None, str]:
    """``(spoken, shown)`` for the whole *text*.

    *spoken* is ``None`` when the reply opens no block at all: the whole reply
    is meant for the ear then, as it was before the block existed. An empty
    block reads as ``""`` instead — the model said nothing is to be read
    aloud, which is not the same thing as saying nothing about it.

    The whole reply is in hand, so prose in front of the first block is known to
    be for the eye alone and stays unspoken; a stream cannot know that
    (`SpokenSplitter`).
    """
    splitter = SpokenSplitter()
    if OPEN_TAG in text:
        splitter.speak_only_blocks()
    shown, spoken = splitter.feed(text)
    rest_shown, rest_spoken = splitter.flush()
    shown, spoken = shown + rest_shown, spoken + rest_spoken
    if OPEN_TAG not in text:
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
    read whole as it was before the block existed. `speak_only_blocks` drops
    that, for a caller holding the whole reply, which knows whether a block is
    coming.
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
            found = _next_tag(text, cursor)
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


def _split_partial_tag(text: str) -> tuple[str, str]:
    """*text* split before a tail that could still turn out to be a marker.
    Those characters settle nothing yet, so they are held back."""
    for size in range(min(len(text), _LONGEST_PARTIAL_TAG), 0, -1):
        tail = text[-size:]
        if any(len(tail) < len(tag) and tag.startswith(tail) for tag in _TAGS):
            return text[:-size], tail
    return text, ""
