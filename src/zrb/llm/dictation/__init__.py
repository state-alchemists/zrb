"""Speech-to-text for chat sessions: `enable_dictation` adds push-to-talk and
hands-free voice input."""

from zrb.llm.dictation.backend import (
    AnyDictationBackend,
    GoogleDictationBackend,
    MultimodalDictationBackend,
    OpenAIDictationBackend,
    VoskDictationBackend,
)
from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.feature import enable_dictation
from zrb.llm.dictation.listen import listen, record

__all__ = [
    "AnyDictationBackend",
    "DictationConfig",
    "GoogleDictationBackend",
    "MultimodalDictationBackend",
    "OpenAIDictationBackend",
    "VoskDictationBackend",
    "enable_dictation",
    "listen",
    "record",
]
