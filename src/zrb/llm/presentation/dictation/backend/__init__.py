from zrb.llm.presentation.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.presentation.dictation.backend.any_transcription_stream import AnyTranscriptionStream
from zrb.llm.presentation.dictation.backend.builtin import get_dictation_backend
from zrb.llm.presentation.dictation.backend.google import GoogleDictationBackend
from zrb.llm.presentation.dictation.backend.multimodal import MultimodalDictationBackend
from zrb.llm.presentation.dictation.backend.openai import OpenAIDictationBackend
from zrb.llm.presentation.dictation.backend.sensevoice import SenseVoiceDictationBackend
from zrb.llm.presentation.dictation.backend.vosk import VoskDictationBackend

__all__ = [
    "AnyDictationBackend",
    "AnyTranscriptionStream",
    "GoogleDictationBackend",
    "MultimodalDictationBackend",
    "OpenAIDictationBackend",
    "SenseVoiceDictationBackend",
    "VoskDictationBackend",
    "get_dictation_backend",
]
