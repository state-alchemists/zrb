"""The emotions zrb knows, and the emoji the model's reply opens with to
carry one.

The names are VRM 1.0's preset expressions, so an avatar can show one as it
is. The emoji is the model's only way to say it; `reply.ReplyEmotion` takes
it out of the reply before the user sees it. The user's tone never travels
this way; dictation hears it and the turn carries it (`InputProvenance.tone`).
"""

from __future__ import annotations

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


def get_leading_emotion(text: str) -> str | None:
    """The emotion of the emoji *text* opens with, if it opens with one."""
    return _EMOTION_BY_EMOJI.get(text.lstrip()[:1])
