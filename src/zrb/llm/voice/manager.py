"""Building the speech service a config names.

Nothing is discovered here: a speech service is either built into zrb or
registered by a project, so a manager's work is building one and saying what
went wrong — not scanning. It composes a registry (`registry.py`) and delegates
every name lookup to it, so a `register` from `zrb_init.py` is what the next
build reads.

The manager is what a feature talks to: `stt_manager.create_service(name, config)`
returns a Pipecat `STTService`, or raises saying which package is missing, which
is the difference between "the voice did not start" and "the voice did not start
because faster-whisper is not installed".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, TypeAlias, TypeVar, Union, cast

from zrb.llm.voice.registry import (
    SpeechServiceRegistry,
    STTServiceRegistry,
    TTSServiceRegistry,
    stt_registry,
    tts_registry,
)
from zrb.llm.voice.spec import STTServiceSpec, TTSServiceSpec

if TYPE_CHECKING:
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
        # The registry's kind is what `T` says it is, and this is where the two
        # are tied together once: a manager built with the other kind would
        # answer with the wrong spec. The cast is unchecked because a caller
        # passing the wrong registry is a mistake no runtime check would catch
        # sooner than the first `create_service`.
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

        ``None`` is a real answer: a name that is neither built in nor
        registered is a config value that names nothing, and the caller decides
        whether that is a fallback (dictation) or an error (speech).
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
        return f"{spec.name} ({where}): {spec.doc}{missing}"

    def list_lines(self) -> list[str]:
        """Every service, one line each, in name order."""
        return [self.describe(name) for name in self._registry.names()]

    def create_service(
        self, name: str, config: ServiceConfig
    ) -> "STTService | TTSService":
        """The Pipecat service *name* builds with *config*, or a raise saying why not.

        A service whose package is not installed is reported before the factory
        runs: its import would fail with a `ModuleNotFoundError` naming a module
        zrb never asked for, where this names the setting and what to install.
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
        # The factory is the union of both sides': only the spec that resolved
        # knows which config its own factory takes, and that is the one it gets.
        factory = cast(
            "Callable[[ServiceConfig], STTService | TTSService]", spec.factory
        )
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
