from abc import ABC, abstractmethod

from zrb.helper.typing import Any, List, Mapping

# flake8: noqa E501


class AnyInput(ABC):
    """
    Abstract base class representing a generalized input specification.
    This class serves as a template for creating various input types,
    providing a standardized interface for input handling and processing.

    """

    @abstractmethod
    def get_name(self) -> str:
        """
        Retrieves the name of the input.

        Returns:
            str: The name of the input.
        """
        pass

    @abstractmethod
    def get_default(self) -> Any:
        """
        Obtains the default value of the input.

        Returns:
            Any: The default value of the input. The type can be any, depending on the input specification.
        """
        pass

    @abstractmethod
    def get_param_decl(self) -> List[str]:
        """
        Fetches a list of parameter option associated with the input (i.e., `-f` or `--file`).

        Returns:
            List[str]: A list containing strings of parameter options.
        """
        pass

    @abstractmethod
    def get_options(self) -> Mapping[str, Any]:
        """
        Provides a mapping (dictionary) representing the input.

        Returns:
            Mapping[str, Any]: A dictionary where keys are option names and values are the corresponding details.
        """
        pass

    @abstractmethod
    def should_render(self) -> bool:
        """
        Determines whether or not the input should be rendered.

        Returns:
            bool: True if the input should be rendered, False otherwise.
        """
        pass

    @abstractmethod
    def is_hidden(self) -> bool:
        """
        Checks whether the input value is meant to be hidden from view or output.

        Returns:
            bool: True if the input is hidden, False otherwise.
        """
        pass
