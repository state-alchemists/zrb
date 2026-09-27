from zrb.llm.speech.backend.any_speech_backend import AnySpeechBackend
from zrb.llm.speech.backend.builtin import get_speech_backend
from zrb.llm.speech.backend.gemini import GeminiSpeechBackend
from zrb.llm.speech.backend.local_command import LocalCommandBackend
from zrb.llm.speech.backend.openai import OpenAISpeechBackend
from zrb.llm.speech.backend.termux import TermuxSpeechBackend
from zrb.llm.speech.backend.utterance import Utterance, create_wav_utterance

__all__ = [
    "AnySpeechBackend",
    "GeminiSpeechBackend",
    "LocalCommandBackend",
    "OpenAISpeechBackend",
    "TermuxSpeechBackend",
    "Utterance",
    "create_wav_utterance",
    "get_speech_backend",
]
