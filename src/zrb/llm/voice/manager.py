"""Builds the speech service a config names.

A service is built in or registered by a project. Missing packages are reported
by name before the factory runs.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, TypeAlias, TypeVar, Union, cast

from zrb.config.config import CFG
from zrb.llm.util.model_load import heavy_model_load
from zrb.llm.voice.registry import (
    SpeechServiceRegistry,
    STTServiceRegistry,
    TTSServiceRegistry,
    stt_registry,
    tts_registry,
)
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec

if TYPE_CHECKING:
    from loguru import Message, Record
    from pipecat.services.stt_service import STTService
    from pipecat.services.tts_service import TTSService

    from zrb.llm.dictation.config import DictationConfig
    from zrb.llm.speech.config import SpeechConfig

T = TypeVar("T", STTServiceSpec, TTSServiceSpec)

#: Either session's config: a service is built from whichever of the two the
#: side it serves owns, and which of its fields it reads is the spec's business.
#: Written as a string, because both features import this module's package
#: rather than the other way round.
ServiceConfig: TypeAlias = "DictationConfig | SpeechConfig"

#: Either registry: a manager reads one kind, and knows which by its spec type.
AnyServiceRegistry: TypeAlias = Union[STTServiceRegistry, TTSServiceRegistry]


class SpeechServiceManager(Generic[T]):
    """Builds the speech service a name resolves to, and reports the choices."""

    def __init__(self, registry: AnyServiceRegistry) -> None:
        # The cast ties the registry's kind to `T`; a wrong registry is a caller error.
        self._registry: "SpeechServiceRegistry[T]" = cast(
            "SpeechServiceRegistry[T]", registry
        )

    @property
    def registry(self) -> "SpeechServiceRegistry[T]":
        """The canonical service collection this manager reads and writes."""
        return self._registry

    def register(self, name: str, spec: T) -> None:
        """Register *spec* under *name*, replacing any built-in of that name."""
        self._registry.register(name, spec)

    def get_spec(self, name: str) -> "T | None":
        """The spec *name* resolves to, or ``None`` when nothing is registered.

        The caller decides whether an unknown name is a fallback or an error.
        """
        return self._registry.get(name)

    def names(self) -> list[str]:
        """Every service name, sorted, for a message that lists the choices."""
        return self._registry.names()

    def describe(self, name: str) -> str:
        """One line naming *name*, where it runs, and what it is."""
        spec = self._registry.get(name)
        if spec is None:
            return f"{name}: not a registered speech service"
        where = "local" if spec.is_local else "remote"
        missing = "" if spec.is_available else f" (needs {spec.provider})"
        doc = spec.doc.replace("{ENV_PREFIX}", CFG.ENV_PREFIX)
        return f"{spec.name} ({where}): {doc}{missing}"

    def list_lines(self) -> list[str]:
        """Every service, one line each, in name order."""
        return [self.describe(name) for name in self._registry.names()]

    def create_service(
        self, name: str, config: ServiceConfig
    ) -> "STTService | TTSService":
        """The Pipecat service *name* builds with *config*, or raises why not.

        A missing package is reported before the factory runs.
        """
        spec = self._registry.get(name)
        if spec is None:
            raise ValueError(
                f"unknown speech service {name!r}: use one of "
                f"{', '.join(self._registry.names())}, or register your own "
                "(see zrb.llm.voice)"
            )
        if spec.factory is None:
            raise ValueError(f"speech service {spec.name!r} has no factory")
        if not spec.is_available:
            raise RuntimeError(
                f"speech service {spec.name!r} needs the {spec.provider!r} "
                "package, which is not installed"
            )
        route_pipecat_logs()
        # The resolved spec determines which config its factory receives.
        factory = cast(
            "Callable[[ServiceConfig], STTService | TTSService]", spec.factory
        )
        if not spec.is_local:
            return factory(config)
        # A local service builds its model here, and a model's load costs far
        # more than the model keeps: one at a time, so two of them never peak
        # together (the memory that costs a chat its life on a small machine).
        with heavy_model_load(f"the {spec.name} service"):
            return factory(config)


class STTServiceManager(SpeechServiceManager[STTServiceSpec]):
    """Builds the speech-to-text service dictation runs on."""

    def create_service(self, name: str, config: ServiceConfig) -> "STTService":
        """The Pipecat `STTService` *name* builds with *config*."""
        return cast("STTService", super().create_service(name, config))


class TTSServiceManager(SpeechServiceManager[TTSServiceSpec]):
    """Builds the text-to-speech service speech runs on."""

    def create_service(self, name: str, config: ServiceConfig) -> "TTSService":
        """The Pipecat `TTSService` *name* builds with *config*."""
        return cast("TTSService", super().create_service(name, config))


#: The speech-to-text manager every session starts from. Import this, not the
#: class, unless a test needs an isolated view.
stt_manager = STTServiceManager(stt_registry)

#: The text-to-speech manager every session starts from.
tts_manager = TTSServiceManager(tts_registry)


@functools.cache
def route_pipecat_logs() -> None:
    """Send what loguru's default sink would write to `logging`, once, before
    Pipecat is imported.

    Pipecat logs through loguru, whose default sink writes every DEBUG line
    to stderr, over the chat UI. Only that sink is replaced: one a project
    added keeps receiving, and when the default is gone already nothing is
    added."""
    # lazy: heavy third-party — loguru comes with pipecat, the voice extra.
    from loguru import logger

    def to_logging(message: "Message") -> None:
        record = message.record
        exception = record["exception"]
        _get_logger(record).log(
            record["level"].no,
            record["message"],
            exc_info=exception.value if exception is not None else None,
        )

    def is_wanted(record: "Record") -> bool:
        # Skip formatting a record `logging` would drop anyway.
        return _get_logger(record).isEnabledFor(record["level"].no)

    try:
        logger.remove(_LOGURU_DEFAULT_SINK)
    except ValueError:
        return
    logger.add(to_logging, level="DEBUG", format="{message}", filter=is_wanted)


def _get_logger(record: "Record") -> logging.Logger:
    return logging.getLogger(record["name"] or "pipecat")


#: The id loguru gives the stderr sink it starts with.
_LOGURU_DEFAULT_SINK = 0
