"""Voice on Pipecat: which speech service zrb runs, and how to add one.

The three names this package exports — :data:`stt_manager`,
:data:`tts_manager` and the two registries behind them — are the extension
point for the models a session speaks and listens through. A project picks one
with `ZRB_LLM_DICTATION_BACKEND` / `ZRB_LLM_SPEECH_BACKEND`, or registers its own
from `zrb_init.py`::

    from zrb import tts_manager
    from zrb.llm.voice.spec import TTSServiceSpec

    tts_manager.register("my-voice", TTSServiceSpec(
        name="my-voice",
        provider="my_voice_sdk",
        factory=lambda config: MyTTSService(api_key="...", voice=config.voice),
    ))

What is registered here is *which service*; what zrb makes of its output — wake
words, stop words, approvals, when speech pauses — stays zrb's.
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
