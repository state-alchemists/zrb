"""Registries of speech-to-text and text-to-speech services.

A registry holds built-ins and code registrations; it does not build services.
A project registration replaces a built-in of the same name.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from zrb.llm.voice.builtin import STT_SERVICE_SPECS, TTS_SERVICE_SPECS
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec

T = TypeVar("T", STTServiceSpec, TTSServiceSpec)


class SpeechServiceRegistry(Generic[T]):
    """Named speech services: built-in defaults plus code registrations.

    Module-level instances are the canonical registries; fresh instances are for
    isolated tests.
    """

    def __init__(self, builtins: "dict[str, T]") -> None:
        self._builtins = builtins
        self._registered: "dict[str, T]" = {}

    def register(self, name: str, spec: T) -> None:
        """Register *spec* under *name*, replacing any built-in or earlier one.

        Names are normalized for registration and lookup.
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
