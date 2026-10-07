"""Pin built-in TTS voice defaults and configured voice wiring."""

import sys
import types
from typing import Any

from zrb.llm.speech.config import SpeechConfig
from zrb.llm.voice.builtin import TTS_SERVICE_SPECS


class _StubSettings:
    """Stub service settings receiving zrb's voice."""

    def __init__(self) -> None:
        self.voice: str | None = None


def _build(
    name: str,
    config: SpeechConfig,
    monkeypatch: Any,
    module_path: str,
    service_name: str,
) -> "list[Any]":
    """Build a named service with its runtime stubbed."""
    module = types.ModuleType(module_path)
    built: "list[Any]" = []

    class StubService:
        Settings = _StubSettings

        def __init__(self, *, settings: "Any | None" = None, **kwargs: Any) -> None:
            built.append(settings)

    setattr(module, service_name, StubService)
    monkeypatch.setitem(sys.modules, module_path, module)
    factory = TTS_SERVICE_SPECS[name].factory
    assert factory is not None
    factory(config)
    return built


def test_piper_is_named_the_voice_it_needs_when_none_is_configured(monkeypatch):
    built = _build(
        "piper",
        SpeechConfig(voice=""),
        monkeypatch,
        "pipecat.services.piper.tts",
        "PiperTTSService",
    )
    assert [settings.voice for settings in built] == ["en_US-ryan-high"]


def test_kokoro_is_named_the_voice_it_needs_when_none_is_configured(monkeypatch):
    built = _build(
        "kokoro",
        SpeechConfig(voice=""),
        monkeypatch,
        "pipecat.services.kokoro.tts",
        "KokoroTTSService",
    )
    assert [settings.voice for settings in built] == ["af_heart"]


def test_a_configured_voice_wins_over_the_default(monkeypatch):
    built = _build(
        "piper",
        SpeechConfig(voice="  en_GB-alan-low  "),
        monkeypatch,
        "pipecat.services.piper.tts",
        "PiperTTSService",
    )
    assert [settings.voice for settings in built] == ["en_GB-alan-low"]


def test_a_service_with_a_default_of_its_own_is_left_to_it(monkeypatch):
    """Pocket keeps its own default when zrb has no voice."""
    built = _build(
        "pocket",
        SpeechConfig(voice=""),
        monkeypatch,
        "pipecat.services.pocket_tts.tts",
        "PocketTTSService",
    )
    assert built == [None]
