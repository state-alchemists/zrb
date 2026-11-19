"""Text-to-speech for chat sessions: `enable_speech` reads replies, tool
approvals and questions aloud."""

from zrb.llm.presentation.speech.backend import (
    AnySpeechBackend,
    GeminiSpeechBackend,
    LocalCommandBackend,
    OpenAISpeechBackend,
    TermuxSpeechBackend,
    Utterance,
)
from zrb.llm.presentation.speech.config import SpeechConfig
from zrb.llm.presentation.speech.feature import (
    enable_speech,
    interrupt_speech,
    pause_speech,
    resume_speech,
)
from zrb.llm.presentation.speech.player import Speaker, is_speaking

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
    "interrupt_speech",
    "is_speaking",
    "pause_speech",
    "resume_speech",
]
