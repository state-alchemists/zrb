"""Voice on Pipecat: which speech service zrb runs, and how to add one.

Projects select a service with `ZRB_LLM_DICTATION_BACKEND` /
`ZRB_LLM_SPEECH_BACKEND` or register one from `zrb_init.py`.
"""

from zrb.llm.voice.manager import (
    STTServiceManager,
    TTSServiceManager,
    stt_manager,
    tts_manager,
)
from zrb.llm.voice.registry import (
    STTServiceRegistry,
    TTSServiceRegistry,
    stt_registry,
    tts_registry,
)
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec

__all__ = [
    "STTServiceManager",
    "STTServiceRegistry",
    "STTServiceSpec",
    "TTSServiceManager",
    "TTSServiceRegistry",
    "TTSServiceSpec",
    "stt_manager",
    "stt_registry",
    "tts_manager",
    "tts_registry",
]
