from __future__ import annotations

from typing import Protocol


class AnySubAgentDefinition(Protocol):
    name: str
    description: str
    path: str
