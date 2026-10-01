from __future__ import annotations

from typing import Any

from zrb.llm.dictation.echo.any_echo_canceller import AnyEchoCanceller


class NoEchoCanceller(AnyEchoCanceller):
    """Trusts the microphone: headphones, or the system already cancels
    echo (PipeWire's or PulseAudio's echo-cancel module, a headset)."""

    @property
    def name(self) -> str:
        return "none"

    @property
    def needs_reference(self) -> bool:
        return False

    def process(self, mic: Any, far: Any) -> Any:
        return mic
