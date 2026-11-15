from __future__ import annotations

from abc import ABC, abstractmethod


class AnyCameraBackend(ABC):
    """Something that can take a photo."""

    @property
    def name(self) -> str:
        """How the backend is called in messages."""
        return type(self).__name__

    @abstractmethod
    async def capture(self, device: str | None) -> bytes | None:
        """One JPEG from *device* (the backend's default when ``None``), or
        ``None`` on failure. Never raises; `get_failure_hint` explains."""

    def list_devices(self) -> list[str]:
        """Device ids or names to offer for completion. Must not block."""
        return []

    async def refresh_devices(self) -> list[str]:
        """The same names, asked for fresh where listing them is slow or cached.

        The default is `list_devices`, which is right for a backend whose list is
        immediate. One that probes in the background — a slow platform-specific
        listing that lands after the fast one — overrides this, so a caller with a
        deadline can ask for the settled list before believing a name is missing.
        """
        return self.list_devices()

    def get_failure_hint(self) -> str:
        """What to do after `capture` returned ``None``."""
        return ""
