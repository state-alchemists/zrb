from abc import ABC, abstractmethod

from zrb.context.any_shared_context import AnySharedContext


class AnyEnv(ABC):
    @abstractmethod
    def update_context(self, shared_ctx: AnySharedContext):
        """Write this env's variables onto `shared_ctx.env`.

        Called during task setup; later envs overwrite earlier ones on a name
        collision.
        """
