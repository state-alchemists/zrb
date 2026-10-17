from __future__ import annotations

from abc import ABC, abstractmethod


class AnyScreenshotBackend(ABC):
    """Something that can capture the screen."""

    @property
    def name(self) -> str:
        """How the backend is called in messages."""
        return type(self).__name__

    @abstractmethod
    async def capture(self, display: str | None) -> bytes | None:
        """One PNG or JPEG of *display* (the main screen when ``None``), or
        ``None`` on failure. Never raises; `get_failure_hint` explains."""

    def list_displays(self) -> list[str]:
        """Display names to offer for completion. Must not block."""
        return []

    def get_failure_hint(self) -> str:
        """What to do after `capture` returned ``None``."""
        return ""
