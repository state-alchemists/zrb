from abc import ABC, abstractmethod

from ..context.any_context import AnyContext


class AnyTransformer(ABC):
    @abstractmethod
    def match(self, ctx: AnyContext, file_path: str) -> bool:
        """
        Determine whether a file path should be processed or not

        Args:
            ctx (AnyContext): The context
            file_path(str): The file path

        Returns:
            bool: Whether the file path should be processed or not
        """
        pass

    @abstractmethod
    def transform_file(self, ctx: AnyContext, file_path: str):
        """
        Transform  the file path

        Args:
            ctx (AnyContext): The context
            file_path(str): The file path
        """
        pass
