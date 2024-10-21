from typing import Any
from abc import ABC, abstractmethod
from collections.abc import Mapping


class AnySharedContext(ABC):
    @abstractmethod
    def render(self, template: str, additional_data: Mapping[str, Any] = {}) -> str:
        pass
