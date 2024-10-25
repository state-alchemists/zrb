from abc import ABC, abstractmethod
from ..session.any_shared_context import AnySharedContext


class AnyEnv(ABC):
    @abstractmethod
    def update_shared_context(self, shared_context: AnySharedContext):
        pass
