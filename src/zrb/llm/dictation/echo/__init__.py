"""Echo cancellation for barge-in: removing zrb's own voice from what the
microphone hears, so the user can talk over zrb on speakers."""

from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller
from zrb.llm.dictation.echo.builtin import get_echo_canceller
from zrb.llm.dictation.echo.cancellation import EchoCancellation
from zrb.llm.dictation.echo.none import NoEchoCanceller

__all__ = [
    "AnyEchoCanceller",
    "EchoCancellation",
    "NoEchoCanceller",
    "get_echo_canceller",
]
