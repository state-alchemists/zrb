"""Emotion for chat sessions: `enable_emotion` has the model open each reply
with an emoji for how it feels, and fires the `Emotion` hook with the emotion
of each reply and the tone dictation heard each prompt said in."""

from zrb.llm.emotion.config import EmotionConfig
from zrb.llm.emotion.feature import enable_emotion
from zrb.llm.emotion.label import get_leading_emotion

__all__ = [
    "EmotionConfig",
    "enable_emotion",
    "get_leading_emotion",
]
