from abc import ABC, abstractmethod

from zrb.context.any_context import AnyContext


class AnyContentTransformer(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Transformer's name"""
        pass

    @abstractmethod
    def match(self, ctx: AnyContext, file_path: str) -> bool:
        """Whether *file_path* is one this transformer rewrites."""
        pass

    @abstractmethod
    def transform_file(self, ctx: AnyContext, file_path: str):
        """Rewrite *file_path* in place. Called only when `match` is True."""
        pass
