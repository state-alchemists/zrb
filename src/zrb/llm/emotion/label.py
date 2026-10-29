"""The emotions zrb knows, and the emoji the model's reply opens with to
carry one.

The names are VRM 1.0's preset expressions, so an avatar can show one as it
is. The emoji is the model's only way to say it; `reply.ReplyEmotion` takes
it out of the reply before the user sees it. The user's tone never travels
this way; dictation hears it and the turn carries it (`InputProvenance.tone`).
"""

from __future__ import annotations

from zrb.llm.util.spoken import OPEN_TAG

# The emoji recognized for each emotion. The first is the one the prompt
# asks for.
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


# Markdown emphasis or code markers a reply may open with *in front of* the
# emoji. A model bolds its opening line by habit, so `**😊 …` opens with an
# emoji exactly as `😊 …` does: the markers are skipped here and left in the
# text, so the emphasis keeps its closing pair.
OPENING_MARKERS = "*_`"


def leading_emoji_index(text: str) -> int | None:
    """Index in *text* of the emotion emoji it opens with, if it opens with
    one: the whitespace, the markdown emphasis or code markers immediately in
    front of it, and a `<spoken>` block's opening marker are skipped — with
    speech on, the emoji is the block's first character, not the reply's. A
    bullet or heading marker is not handled, and neither is whitespace between
    the markers and the emoji."""
    index = _opening_start(text, len(text) - len(text.lstrip()))
    if index < len(text) and text[index] in _EMOTION_BY_EMOJI:
        return index
    return None


def get_leading_emotion(text: str) -> str | None:
    """The emotion of the emoji *text* opens with, if it opens with one."""
    index = leading_emoji_index(text)
    return None if index is None else _EMOTION_BY_EMOJI[text[index]]


def opening_tag_index(text: str) -> int | None:
    """Where a `<spoken>` block opens *text*, past the whitespace before it:
    the reply's first characters then, and the emoji's place is inside it."""
    index = len(text) - len(text.lstrip())
    if not text.startswith(OPEN_TAG, index):
        return None
    return index


def _opening_start(text: str, index: int) -> int:
    """Where what the reply opens with begins, from *index*: past a `<spoken>`
    marker and any markdown markers, in either order."""
    while index < len(text):
        if text.startswith(OPEN_TAG, index):
            index += len(OPEN_TAG)
        elif text[index] in OPENING_MARKERS:
            index += 1
        else:
            return index
    return index
