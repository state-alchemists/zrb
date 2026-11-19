from zrb.llm.presentation.speech.backend.any_speech_backend import (
    AnySpeechBackend,
    SpeechServiceStopped,
)
from zrb.llm.presentation.speech.backend.builtin import get_speech_backend
from zrb.llm.presentation.speech.backend.gemini import GeminiSpeechBackend
from zrb.llm.presentation.speech.backend.local_command import LocalCommandBackend
from zrb.llm.presentation.speech.backend.openai import OpenAISpeechBackend
from zrb.llm.presentation.speech.backend.termux import TermuxSpeechBackend
from zrb.llm.presentation.speech.backend.utterance import (
    Utterance,
    create_wav_utterance,
)

__all__ = [
    "AnySpeechBackend",
    "GeminiSpeechBackend",
    "LocalCommandBackend",
    "OpenAISpeechBackend",
    "SpeechServiceStopped",
    "TermuxSpeechBackend",
    "Utterance",
    "create_wav_utterance",
    "get_speech_backend",
]
