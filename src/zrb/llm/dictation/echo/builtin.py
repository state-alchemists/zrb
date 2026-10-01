from __future__ import annotations

from zrb.llm.dictation.config import DictationConfig
from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller
from zrb.llm.dictation.echo.none import NoEchoCanceller


def get_echo_canceller(
    canceller: "str | AnyEchoCanceller", config: DictationConfig | None = None
) -> AnyEchoCanceller:
    """*canceller* itself, or the built-in one it names: ``numpy`` (cancels
    zrb's voice out of the microphone, tuned by *config*) or ``none``
    (trusts the microphone: headphones, or the system cancels echo)."""
    if isinstance(canceller, AnyEchoCanceller):
        return canceller
    name = canceller.strip().lower() or "numpy"
    if name == "numpy":
        # lazy: heavy third-party (numpy); a canceller is built only when
        # barge-in is on.
        from zrb.llm.dictation.echo.numpy_canceller import NumpyEchoCanceller

        return NumpyEchoCanceller(config)
    if name == "none":
        return NoEchoCanceller()
    raise ValueError(
        f"unknown echo canceller {canceller!r}: use numpy, none, or an "
        "AnyEchoCanceller"
    )
