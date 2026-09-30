from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.any_transcription_stream import AnyTranscriptionStream
from zrb.llm.dictation.backend.builtin import get_dictation_backend
from zrb.llm.dictation.backend.google import GoogleDictationBackend
from zrb.llm.dictation.backend.multimodal import MultimodalDictationBackend
from zrb.llm.dictation.backend.openai import OpenAIDictationBackend
from zrb.llm.dictation.backend.vosk import VoskDictationBackend

__all__ = [
    "AnyDictationBackend",
    "AnyTranscriptionStream",
    "GoogleDictationBackend",
    "MultimodalDictationBackend",
    "OpenAIDictationBackend",
    "VoskDictationBackend",
    "get_dictation_backend",
]
