"""Speech-to-text for chat sessions: `enable_dictation` adds push-to-talk and
hands-free voice input."""

from zrb.llm.dictation.backend import (
    AnyDictationBackend,
    AnyTranscriptionStream,
    GoogleDictationBackend,
    MultimodalDictationBackend,
    OpenAIDictationBackend,
    VoskDictationBackend,
)
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.feature import enable_dictation
from zrb.llm.dictation.listen import MicState, listen, record

__all__ = [
    "AnyDictationBackend",
    "AnyTranscriptionStream",
    "DictationConfig",
    "GoogleDictationBackend",
    "MicState",
    "MultimodalDictationBackend",
    "OpenAIDictationBackend",
    "VoskDictationBackend",
    "enable_dictation",
    "listen",
    "record",
]
