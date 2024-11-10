from abc import ABC, abstractmethod

from ..context.any_shared_context import AnySharedContext


class AnyEnv(ABC):
    @abstractmethod
    def update_context(self, shared_ctx: AnySharedContext):
        pass
