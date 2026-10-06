from unittest.mock import patch

import pytest

from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.builtin import get_dictation_backend
from zrb.llm.dictation.backend.google import GoogleDictationBackend
from zrb.llm.dictation.backend.multimodal import MultimodalDictationBackend
from zrb.llm.dictation.backend.openai import OpenAIDictationBackend
from zrb.llm.dictation.backend.pipecat import PipecatDictationBackend
from zrb.llm.dictation.backend.vosk import VoskDictationBackend
from zrb.llm.dictation.config import DictationConfig

MODULE = "zrb.llm.dictation.backend.builtin"


class EchoBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


def _config(**kwargs):
    return DictationConfig(**kwargs).resolve()


@pytest.mark.parametrize(
    "name, expected",
    [
        ("vosk", VoskDictationBackend),
        ("", VoskDictationBackend),
        (" OpenAI ", OpenAIDictationBackend),
        ("google", GoogleDictationBackend),
        ("multimodal", MultimodalDictationBackend),
        ("whisper", PipecatDictationBackend),
        (" Moonshine ", PipecatDictationBackend),
        ("funasr", PipecatDictationBackend),
    ],
)
def test_dispatches_by_name(name, expected):
    assert isinstance(get_dictation_backend(name, _config()), expected)


def test_passes_a_backend_instance_through():
    backend = EchoBackend()
    assert get_dictation_backend(backend, _config()) is backend


def test_a_pipecat_backend_is_named_after_the_service_it_was_given():
    """The name a config gives is the service the pipeline is built from.

    The backend resolves nothing itself: `zrb.llm.voice`'s manager does, so a
    service registered in `zrb_init.py` is reachable by the same setting as the
    built-in models, and a name neither is fails there with the package to
    install rather than here.
    """
    backend = get_dictation_backend("moonshine", _config())
    assert isinstance(backend, PipecatDictationBackend)
    assert backend.name == "Pipecat (moonshine)"


def test_unknown_name_raises():
    with pytest.raises(ValueError, match="unknown dictation backend 'nonesuch'"):
        get_dictation_backend("nonesuch", _config())


def test_an_unknown_name_is_told_what_the_choices_are():
    """The names a config may carry include the registered speech services."""
    with pytest.raises(ValueError) as raised:
        get_dictation_backend("nonesuch", _config())
    for name in ("vosk", "openai", "google", "multimodal", "whisper", "moonshine"):
        assert name in str(raised.value)


def test_vosk_built_from_config():
    config = _config(
        vosk_model_name="m",
        vosk_model_url="http://host",
        vosk_download_timeout=5,
        vosk_max_download_mb=10,
        vosk_max_uncompressed_mb=20,
        vosk_max_file_mb=15,
        vosk_max_files=7,
        vosk_confidence=0.6,
    )
    with patch(f"{MODULE}.VoskDictationBackend") as vosk:
        get_dictation_backend("vosk", config)
    vosk.assert_called_once_with("m", "http://host", 5, 10, 20, 15, 7, confidence=0.6)


def test_openai_built_from_config():
    config = _config(
        openai_model="gpt-4o-transcribe", openai_base_url="", language="en"
    )
    with patch(f"{MODULE}.OpenAIDictationBackend") as openai:
        get_dictation_backend("openai", config)
    openai.assert_called_once_with(
        "gpt-4o-transcribe", base_url=None, language="en"
    )


def test_google_built_from_config():
    with patch(f"{MODULE}.GoogleDictationBackend") as google:
        get_dictation_backend(
            "google", _config(google_model="gemini-x", transcribe_prompt="Write it.")
        )
    google.assert_called_once_with("gemini-x", instruction="Write it.")


def test_multimodal_built_with_the_configured_prompt():
    with patch(f"{MODULE}.MultimodalDictationBackend") as multimodal:
        get_dictation_backend("multimodal", _config(transcribe_prompt="Write it."))
    multimodal.assert_called_once_with(instruction="Write it.")


def test_default_backend_name_is_class_name():
    backend = EchoBackend()
    assert backend.name == "EchoBackend"


@pytest.mark.asyncio
async def test_default_prepare_does_nothing():
    reports = []
    await EchoBackend().prepare(reports.append)
    assert reports == []
