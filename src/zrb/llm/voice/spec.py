"""What a registered speech service is.

A spec is a registry's unit: the name a config value or a message quotes, the
factory that builds the Pipecat service, and what someone choosing between
services needs — whether it runs on this machine or calls out, the languages it
speaks, and the package whose absence is why it cannot be built here.

The factory imports Pipecat inside its body, so a spec can be written in
`zrb_init.py`, listed, and chosen without the voice stack being importable.
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
    """What every registered speech service has, whichever way it is used.

    *provider* is the importable package the service runs on (``pipecat``'s own
    extra, or a vendor SDK). It is named rather than imported, so
    `is_available` answers without paying for the import.
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

    *factory* is handed the resolved `DictationConfig` and returns a Pipecat
    `STTService`. Every local one of these is a `SegmentedSTTService`:
    it transcribes the audio it has buffered when the segment ends, which is
    the shape zrb's own cutter already delimits.
    """

    factory: Callable[["DictationConfig"], "STTService"] | None = None


@dataclass(frozen=True)
class TTSServiceSpec(SpeechServiceSpec):
    """A text-to-speech service the speech path may be built on.

    *factory* is handed the resolved `SpeechConfig` and returns a Pipecat
    `TTSService`.
    """

    factory: Callable[["SpeechConfig"], "TTSService"] | None = None
