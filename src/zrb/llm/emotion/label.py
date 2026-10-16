"""The emotions zrb shows, and the emoji a reply opens with to carry one.

The names are VRM 1.0's preset expressions, so an avatar can show one as it
is. The emoji carries the model's emotion in its own text: the user sees it
and speech skips it. The user's tone never travels this way; dictation hears
it and the turn carries it (`InputProvenance.tone`).
"""

from __future__ import annotations

# Every emoji read as an emotion. The first of each is the one the model is
# asked to write.
_EMOJI_BY_EMOTION: dict[str, str] = {
    "happy": "😊😄😁😀😃🥰😍",
    "sad": "😢😔😞😭🙁",
    "angry": "😠😡🤬",
    "surprised": "😮😲😯🤯😱",
    "relaxed": "😌",
    "neutral": "🙂😐😶",
}
_EMOTION_BY_EMOJI: dict[str, str] = {
    emoji: emotion for emotion, emojis in _EMOJI_BY_EMOTION.items() for emoji in emojis
}


def get_leading_emotion(text: str) -> str | None:
    """The emotion of the emoji *text* opens with, if it opens with one."""
    return _EMOTION_BY_EMOJI.get(text.lstrip()[:1])


class ReplyOpening:
    """The emotion each text part of a streamed reply opens with, read from
    the run's stream events by tag, not class, so no pydantic-ai import."""

    def __init__(self) -> None:
        self.emotion: str | None = None
        # The opening of the text part being read, until it shows a character.
        self._text: str | None = None

    def read(self, event: object) -> str | None:
        """Read *event*; return the emotion a text part turned out to open
        with, once, as soon as its first character shows it."""
        kind = getattr(event, "event_kind", None)
        part = getattr(event, "part", None)
        delta = getattr(event, "delta", None)
        if kind == "part_start" and getattr(part, "part_kind", None) == "text":
            self._text = getattr(part, "content", "") or ""
            self.emotion = None
        elif (
            kind == "part_delta"
            and self._text is not None
            and getattr(delta, "part_delta_kind", None) == "text"
        ):
            self._text += getattr(delta, "content_delta", "") or ""
        if self._text is None or not self._text.strip():
            return None
        self.emotion = get_leading_emotion(self._text)
        self._text = None
        return self.emotion
