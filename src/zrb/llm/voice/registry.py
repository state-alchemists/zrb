"""The registries of speech-to-text and text-to-speech services.

A registry is the *source of defaults*: the built-ins it is seeded with, plus
everything registered in code, keyed by the name a config value quotes. It does
not build anything — that is the owning manager's job.

A user registration wins over a built-in of the same name, so a project may
replace ``whisper`` with its own service without giving up the built-ins beside
it. `zrb_init.py`::

    from zrb import tts_manager
    from zrb.llm.voice.spec import TTSServiceSpec

    tts_manager.register("my-voice", TTSServiceSpec(
        name="my-voice",
        provider="my_voice_sdk",
        factory=lambda config: MyTTSService(api_key="...", voice=config.voice),
    ))

then ``ZRB_LLM_SPEECH_BACKEND=my-voice``.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from zrb.llm.voice.builtin import STT_SERVICE_SPECS, TTS_SERVICE_SPECS
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec

T = TypeVar("T", STTServiceSpec, TTSServiceSpec)


class SpeechServiceRegistry(Generic[T]):
    """Named speech services: built-in defaults plus registrations in code.

    A single instance per kind is exposed at module level as
    :data:`stt_registry` and :data:`tts_registry` — import those, not the class.
    Construct a fresh instance only in tests that need full isolation.
    """

    def __init__(self, builtins: "dict[str, T]") -> None:
        self._builtins = builtins
        self._registered: "dict[str, T]" = {}

    def register(self, name: str, spec: T) -> None:
        """Register *spec* under *name*, replacing any built-in or earlier one.

        The name is normalized the way a lookup normalizes it, so a
        registration and a config value meet whatever their case and spacing.
        """
        key = _normalize(name)
        if not key:
            raise ValueError("a speech service needs a name to be registered under")
        self._registered[key] = spec

    def get(self, name: str) -> "T | None":
        """The spec registered under *name*, registration first, else a built-in."""
        key = _normalize(name)
        if key in self._registered:
            return self._registered[key]
        return self._builtins.get(key)

    def all(self) -> "dict[str, T]":
        """Every spec, built-in and registered, keyed by its normalized name."""
        return {**self._builtins, **self._registered}

    def names(self) -> list[str]:
        """Every registered name, sorted, for a message that lists the choices."""
        return sorted(self.all())

    def clear(self) -> None:
        """Drop every registration, leaving the built-ins. For tests."""
        self._registered.clear()


class STTServiceRegistry(SpeechServiceRegistry[STTServiceSpec]):
    """The speech-to-text services dictation may be built on."""


class TTSServiceRegistry(SpeechServiceRegistry[TTSServiceSpec]):
    """The text-to-speech services speech may be built on."""


def _normalize(name: str) -> str:
    """*name* as a registry key: trimmed and case-folded."""
    return (name or "").strip().lower()


#: The speech-to-text services every session starts from. Its built-ins are
#: wired in `zrb.llm.voice.builtin`, each importing Pipecat only when built.
stt_registry = STTServiceRegistry(STT_SERVICE_SPECS)

#: The text-to-speech services every session starts from.
tts_registry = TTSServiceRegistry(TTS_SERVICE_SPECS)
