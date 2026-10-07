"""A registered speech service: its name, factory, location, languages and provider.

The factory imports Pipecat inside its body, so a spec can be listed without the
voice stack being importable.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipecat.services.stt_service import STTService
    from pipecat.services.tts_service import TTSService

    from zrb.llm.dictation.config import DictationConfig
    from zrb.llm.speech.config import SpeechConfig


@dataclass(frozen=True)
class SpeechServiceSpec:
    """What every registered speech service has.

    *provider* is named rather than imported, so `is_available` answers without
    importing the service.
    """

    name: str
    provider: str = ""
    is_local: bool = True
    languages: tuple[str, ...] = ()
    doc: str = ""

    @property
    def is_available(self) -> bool:
        """Whether the package this service runs on is installed."""
        if not self.provider:
            return True
        try:
            return importlib.util.find_spec(self.provider) is not None
        except ModuleNotFoundError:
            # A dotted provider whose parent package is missing raises.
            return False


@dataclass(frozen=True)
class STTServiceSpec(SpeechServiceSpec):
    """A speech-to-text service the dictation path may be built on.

    *factory* receives `DictationConfig` and returns a Pipecat `STTService`.
    Local services are `SegmentedSTTService`s; they transcribe buffered audio
    when the segment ends.
    """

    factory: Callable[["DictationConfig"], "STTService"] | None = None


@dataclass(frozen=True)
class TTSServiceSpec(SpeechServiceSpec):
    """A text-to-speech service the speech path may be built on.

    *factory* is handed the resolved `SpeechConfig` and returns a Pipecat
    `TTSService`.
    """

    factory: Callable[["SpeechConfig"], "TTSService"] | None = None
