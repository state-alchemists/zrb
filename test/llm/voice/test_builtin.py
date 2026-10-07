"""What the built-in services are built with.

Kokoro and Piper make the voice mandatory — Pipecat's `require_given` raises
from their constructors — so an empty `ZRB_LLM_SPEECH_VOICE` is not a service
keeping its own choice there, it is a backend that cannot start. These pin the
wiring that makes naming one of them work, and that leaves a service which does
have a default of its own (Pocket) alone.

Neither model runtime is installed to test this: the service class is stubbed,
and what is asserted is the settings zrb hands it. A test leaning on the real
package would pass or fail by what is on the machine.
"""

import sys
import types
from typing import Any

from zrb.llm.speech.config import SpeechConfig
from zrb.llm.voice.builtin import TTS_SERVICE_SPECS


class _StubSettings:
    """Stands in for a service's own `Settings`: the voice is what zrb writes."""

    def __init__(self) -> None:
        self.voice: str | None = None


def _build(
    name: str,
    config: SpeechConfig,
    monkeypatch: Any,
    module_path: str,
    service_name: str,
) -> "list[Any]":
    """Build the built-in *name* with its service stubbed, and return what it got.

    The service is stubbed where the factory imports it, so no model runtime has
    to be installed, and the spec's own factory is used, so what is pinned is the
    wiring that naming *name* really goes through.
    """
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
    """Pocket's own `Settings` defaults the voice to ``alba``, so zrb passes none.

    ``None`` is what "zrb configured nothing here" means: a voice of zrb's own
    would override the default the service was tested with.
    """
    built = _build(
        "pocket",
        SpeechConfig(voice=""),
        monkeypatch,
        "pipecat.services.pocket_tts.tts",
        "PocketTTSService",
    )
    assert built == [None]
