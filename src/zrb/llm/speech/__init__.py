"""Text-to-speech for chat sessions: `enable_speech` reads replies, tool
approvals and questions aloud."""

from zrb.llm.speech.backend import (
    AnySpeechBackend,
    GeminiSpeechBackend,
    LocalCommandBackend,
    OpenAISpeechBackend,
    TermuxSpeechBackend,
    Utterance,
)
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.speech.feature import enable_speech
from zrb.llm.speech.player import Speaker, is_speaking

__all__ = [
    "AnySpeechBackend",
    "GeminiSpeechBackend",
    "LocalCommandBackend",
    "OpenAISpeechBackend",
    "Speaker",
    "SpeechConfig",
    "TermuxSpeechBackend",
    "Utterance",
    "enable_speech",
    "is_speaking",
]
