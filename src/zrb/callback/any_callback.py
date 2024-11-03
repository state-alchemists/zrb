from typing import Any
from abc import ABC, abstractmethod
from ..context.any_shared_context import AnySharedContext


class AnyCallback(ABC):
    @abstractmethod
    async def async_run(self, parent_ctx: AnySharedContext) -> Any:
        pass
