"""The speech services zrb ships with.

Every one of these is a Pipecat service, built by a factory that imports Pipecat
inside its body: naming a built-in — in the config, in a message, or by listing
this registry — must not cost the voice stack's import, and neither must an
install that never turns voice on.

Only services that run the model here are built in. A cloud service is a
Pipecat service too, and a project that wants one registers it (`registry.py`),
because what it needs — a key, a region, a model it bills per character — is not
something zrb can default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec

if TYPE_CHECKING:
    from pipecat.services.settings import STTSettings, TTSSettings
    from pipecat.services.stt_service import STTService
    from pipecat.services.tts_service import TTSService

    from zrb.llm.dictation.config import DictationConfig
    from zrb.llm.speech.config import SpeechConfig

#: A service's own settings class. Every Pipecat service publishes one, and each
#: subclass adds fields of its own, so the concrete class has to survive this
#: helper: the service refuses a settings object that is not its own.
STTSettingsT = TypeVar("STTSettingsT", bound="STTSettings")
TTSSettingsT = TypeVar("TTSSettingsT", bound="TTSSettings")

#: The voice a local service is built with when `ZRB_LLM_SPEECH_VOICE` is empty.
#: Kokoro and Piper make the voice mandatory — Pipecat's `require_given` raises
#: from their constructors — so unlike the models zrb leaves to the service,
#: leaving this unset is not "the service's own choice", it is a backend that
#: cannot start. Each name is the one that service's own documentation uses.
_KOKORO_DEFAULT_VOICE = "af_heart"
_PIPER_DEFAULT_VOICE = "en_US-ryan-high"


def _stt_settings(
    settings: STTSettingsT, config: "DictationConfig"
) -> "STTSettingsT | None":
    """*settings* with what *config* configures, or ``None`` when it configures none.

    ``None`` is the honest answer when nothing is configured: the service then
    keeps the model and language it was tested with, rather than zrb's guess at
    them. The settings a caller passes in are its own class's, so a service that
    publishes extra fields keeps its own type here.
    """
    model = (config.stt_model or "").strip()
    language = (config.language or "").strip()
    if not model and not language:
        return None
    if model:
        settings.model = model
    if language:
        settings.language = language
    return settings


def _tts_settings(
    settings: TTSSettingsT, config: "SpeechConfig", default_voice: str = ""
) -> "TTSSettingsT | None":
    """*settings* with what *config* configures, or ``None`` when it configures none.

    *default_voice* is what the service is built with when no voice is
    configured. Empty for a service that has a default of its own, which then
    keeps it, so ``None`` still means "zrb configured nothing here".
    """
    voice = (config.voice or "").strip() or default_voice
    if not voice:
        return None
    settings.voice = voice
    return settings


def _create_whisper(config: "DictationConfig") -> "STTService":
    """Faster-Whisper, running locally on ctranslate2."""
    # lazy: heavy third-party — the voice extra's Pipecat and its model stack
    from pipecat.services.whisper.stt import WhisperSTTService

    settings = _stt_settings(WhisperSTTService.Settings(), config)
    if settings is None:
        return WhisperSTTService()
    return WhisperSTTService(settings=settings)


def _create_moonshine(config: "DictationConfig") -> "STTService":
    """Moonshine, ONNX on the CPU: no key, no GPU, the smallest of the three."""
    # lazy: heavy third-party — the voice extra's Pipecat and its model stack
    from pipecat.services.moonshine.stt import MoonshineSTTService

    settings = _stt_settings(MoonshineSTTService.Settings(), config)
    if settings is None:
        return MoonshineSTTService()
    return MoonshineSTTService(settings=settings)


def _create_funasr(config: "DictationConfig") -> "STTService":
    """FunASR's SenseVoiceSmall: multilingual, strongest on Chinese."""
    # lazy: heavy third-party — the voice extra's Pipecat and its model stack
    from pipecat.services.funasr.stt import FunASRSTTService

    settings = _stt_settings(FunASRSTTService.Settings(), config)
    if settings is None:
        return FunASRSTTService()
    return FunASRSTTService(settings=settings)


def _create_kokoro(config: "SpeechConfig") -> "TTSService":
    """Kokoro-82M through kokoro-onnx: neural speech on the CPU."""
    # lazy: heavy third-party — the voice extra's Pipecat and its model stack
    from pipecat.services.kokoro.tts import KokoroTTSService

    settings = _tts_settings(KokoroTTSService.Settings(), config, _KOKORO_DEFAULT_VOICE)
    if settings is None:
        return KokoroTTSService()
    return KokoroTTSService(settings=settings)


def _create_piper(config: "SpeechConfig") -> "TTSService":
    """Piper: the lightest of the local voices, and GPL-3.0 in-process."""
    # lazy: heavy third-party — the voice extra's Pipecat and its model stack
    from pipecat.services.piper.tts import PiperTTSService

    settings = _tts_settings(PiperTTSService.Settings(), config, _PIPER_DEFAULT_VOICE)
    if settings is None:
        return PiperTTSService()
    return PiperTTSService(settings=settings)


def _create_pocket(config: "SpeechConfig") -> "TTSService":
    """Kyutai's Pocket TTS: CPU-only, and the one that clones a voice from a wav."""
    # lazy: heavy third-party — the voice extra's Pipecat and its model stack
    from pipecat.services.pocket_tts.tts import PocketTTSService

    settings = _tts_settings(PocketTTSService.Settings(), config)
    if settings is None:
        return PocketTTSService()
    return PocketTTSService(settings=settings)


#: Speech-to-text, by the name `ZRB_LLM_DICTATION_BACKEND` quotes. Every one is
#: a `SegmentedSTTService`: it transcribes what it has buffered when the
#: segment ends, which is the boundary zrb's own cutter already draws.
STT_SERVICE_SPECS: dict[str, STTServiceSpec] = {
    "whisper": STTServiceSpec(
        name="whisper",
        provider="faster_whisper",
        languages=(),
        doc=(
            "Faster-Whisper on ctranslate2. Multilingual, and the heaviest of "
            "the three: pick a size with ZRB_LLM_DICTATION_STT_MODEL (tiny, "
            "base, small, medium, large-v3; empty uses the service's own)."
        ),
        factory=_create_whisper,
    ),
    "moonshine": STTServiceSpec(
        name="moonshine",
        provider="moonshine_voice",
        languages=("ar", "en", "de", "es", "ja", "ko", "tl", "uk", "vi", "zh"),
        doc=(
            "Moonshine, ONNX on the CPU. The lightest of the three and the "
            "only one with no GPU path at all; English is where its model "
            "range is widest (ZRB_LLM_DICTATION_STT_MODEL: tiny, base, "
            "small-streaming, medium-streaming)."
        ),
        factory=_create_moonshine,
    ),
    "funasr": STTServiceSpec(
        name="funasr",
        provider="funasr",
        languages=("zh", "yue", "en", "ja", "ko"),
        doc=(
            "FunASR's SenseVoiceSmall through PyTorch. Multilingual, strongest "
            "on Chinese, and the fastest to run once loaded."
        ),
        factory=_create_funasr,
    ),
}

#: Text-to-speech, by the name `ZRB_LLM_SPEECH_BACKEND` quotes. The voice is
#: `ZRB_LLM_SPEECH_VOICE`, which each of these reads its own way.
TTS_SERVICE_SPECS: dict[str, TTSServiceSpec] = {
    "kokoro": TTSServiceSpec(
        name="kokoro",
        provider="kokoro_onnx",
        languages=("en", "de", "es", "fr", "it", "pt", "ja", "zh"),
        doc=(
            "Kokoro-82M through kokoro-onnx: neural speech on the CPU, with a "
            "fixed voice list (ZRB_LLM_SPEECH_VOICE, e.g. af_heart) rather than "
            "cloning. Model files download on first use; af_heart is what an "
            "unset voice falls back to."
        ),
        factory=_create_kokoro,
    ),
    "piper": TTSServiceSpec(
        name="piper",
        provider="piper",
        languages=(),
        doc=(
            "Piper, in-process: the lightest local voice and the widest voice "
            "catalogue, at the cost of a GPL-3.0 package inside zrb. The voice "
            "model downloads on first use; en_US-ryan-high is what an unset "
            "voice falls back to."
        ),
        factory=_create_piper,
    ),
    "pocket": TTSServiceSpec(
        name="pocket",
        provider="pocket_tts",
        languages=("en", "fr", "de", "es", "it", "pt"),
        doc=(
            "Kyutai's Pocket TTS. The one that clones: "
            "ZRB_LLM_SPEECH_VOICE may be a predefined name (e.g. alba), a .wav "
            "to clone, an exported .safetensors voice state, or an hf:// path. "
            "Needs PyTorch."
        ),
        factory=_create_pocket,
    ),
}
