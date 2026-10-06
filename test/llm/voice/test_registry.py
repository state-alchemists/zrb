"""The speech service registries and the managers that read them.

What these pin: a built-in is named and listed without the voice stack being
imported, a registration wins over a built-in of the same name, an unknown name
is reported with the choices, and a service whose package is missing is reported
by the package zrb can tell the user to install rather than by a raw import
error.
"""

import subprocess
import sys
from typing import Any, cast

import pytest

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.speech.config import SpeechConfig
from zrb.llm.voice.builtin import STT_SERVICE_SPECS, TTS_SERVICE_SPECS
from zrb.llm.voice.manager import STTServiceManager, TTSServiceManager
from zrb.llm.voice.registry import STTServiceRegistry, TTSServiceRegistry
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec


def _stt_manager() -> STTServiceManager:
    return STTServiceManager(STTServiceRegistry(dict(STT_SERVICE_SPECS)))


def _tts_manager() -> TTSServiceManager:
    return TTSServiceManager(TTSServiceRegistry(dict(TTS_SERVICE_SPECS)))


def test_the_built_ins_are_the_local_services_pipecat_ships():
    assert sorted(STT_SERVICE_SPECS) == ["funasr", "moonshine", "whisper"]
    assert sorted(TTS_SERVICE_SPECS) == ["kokoro", "piper", "pocket"]
    assert all(spec.is_local for spec in STT_SERVICE_SPECS.values())
    assert all(spec.is_local for spec in TTS_SERVICE_SPECS.values())


def test_naming_a_built_in_does_not_import_the_voice_stack():
    """A registry is read at startup and inside messages, so listing stays cheap.

    Run in a fresh interpreter: another test in this session may already have
    imported pipecat, which would make the assertion here vacuous.
    """
    code = (
        "import sys; import zrb.llm.voice as voice;"
        "print('pipecat' in sys.modules, voice.stt_manager.names(),"
        " voice.tts_manager.names())"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == (
        "False ['funasr', 'moonshine', 'whisper'] ['kokoro', 'piper', 'pocket']"
    )


def test_a_registration_is_what_the_next_lookup_sees():
    manager = _stt_manager()
    mine = STTServiceSpec(name="my-stt", provider="")
    manager.register("my-stt", mine)
    assert manager.get_spec("my-stt") is mine
    assert "my-stt" in manager.names()


def test_a_registration_replaces_a_built_in_of_the_same_name():
    manager = _tts_manager()
    built = object()
    mine = TTSServiceSpec(
        name="kokoro", provider="", factory=lambda config: cast(Any, built)
    )
    manager.register("kokoro", mine)
    assert manager.get_spec("kokoro") is mine
    assert manager.create_service("kokoro", SpeechConfig()) is built


def test_a_registered_factory_is_handed_the_config_it_asks_for():
    manager = _stt_manager()
    seen: "list[Any]" = []
    manager.register(
        "mine",
        STTServiceSpec(
            name="mine",
            provider="",
            factory=lambda config: cast(Any, seen.append(config)),
        ),
    )
    config = DictationConfig(language="id")
    manager.create_service("mine", config)
    assert seen == [config]


def test_a_name_is_read_however_it_is_cased_or_spaced():
    manager = _tts_manager()
    assert manager.get_spec("  KoKoRo ") is TTS_SERVICE_SPECS["kokoro"]


def test_an_unknown_name_is_reported_with_the_choices():
    manager = _stt_manager()
    assert manager.get_spec("nope") is None
    with pytest.raises(ValueError) as raised:
        manager.create_service("nope", DictationConfig())
    assert "funasr, moonshine, whisper" in str(raised.value)


def test_a_service_whose_package_is_missing_names_the_package():
    """The failure a user can act on, not the `ModuleNotFoundError` underneath it.

    The spec is registered here rather than read off the built-ins: whether
    `moonshine_voice` or `piper` is installed is a fact about the machine, so a
    test that leaned on it would pass or fail by accident.
    """
    manager = STTServiceManager(
        STTServiceRegistry(
            {
                "ghost": STTServiceSpec(
                    name="ghost", provider="zrb_no_such_package", factory=_unbuildable
                )
            }
        )
    )
    with pytest.raises(RuntimeError) as raised:
        manager.create_service("ghost", DictationConfig())
    assert "zrb_no_such_package" in str(raised.value)


def _unbuildable(config: "DictationConfig") -> Any:
    """A factory that must never run: the missing package is reported first."""
    raise AssertionError("the factory ran for a service that cannot be built")


def test_a_service_whose_package_is_missing_is_said_so_when_described():
    """What a listing says a service needs, and where it runs."""
    manager = TTSServiceManager(
        TTSServiceRegistry(
            {
                "ghost": TTSServiceSpec(
                    name="ghost", provider="zrb_no_such_package", is_local=False
                ),
                "here": TTSServiceSpec(name="here"),
            }
        )
    )
    assert manager.describe("ghost").endswith("(needs zrb_no_such_package)")
    assert manager.describe("ghost").startswith("ghost (remote)")
    assert "local" in manager.describe("here")


def test_an_unregistered_name_is_described_as_such():
    manager = _tts_manager()
    assert manager.describe("nope") == "nope: not a registered speech service"


def test_dropping_the_registrations_leaves_the_built_ins():
    registry = STTServiceRegistry(dict(STT_SERVICE_SPECS))
    registry.register("mine", STTServiceSpec(name="mine", provider=""))
    registry.clear()
    assert registry.get("mine") is None
    assert sorted(registry.names()) == ["funasr", "moonshine", "whisper"]


def test_a_registration_needs_a_name():
    registry = TTSServiceRegistry(dict(TTS_SERVICE_SPECS))
    with pytest.raises(ValueError):
        registry.register("  ", TTSServiceSpec(name="nameless", provider=""))


def test_a_spec_without_a_provider_is_available_but_a_named_one_is_checked():
    assert STTServiceSpec(name="mine", provider="").is_available
    assert not STTServiceSpec(name="mine", provider="no_such_package_here").is_available
