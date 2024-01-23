import os

from zrb.helper.string.modification import double_quote
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import JinjaTemplate, Optional
from zrb.task_env.constant import RESERVED_ENV_NAMES

# flake8: noqa E501


@typechecked
class Env:
    """
    Env Represents an environment configuration for a task, encapsulating details such as environment name, OS-specific
    environment name, default values, and rendering behavior.

    Attributes:
        name (str): Environment name as recognized by the task.
        os_name (Optional[str]): The corresponding name in the OS's environment, if different from 'name'. You can set os_name to empty string if you don't want the environment to be linked to OS environment name.
        default (JinjaTemplate): Default value of the environment variable.
        should_render (bool): Flag to determine if the environment value should be rendered.

    Examples:
        >>> from zrb import Env, Task
        >>> task = Task(
        >>>     name='task',
        >>>     envs=[
        >>>         Env(name='DATABASE_URL', os_name='SYSTEM_DATABASE_URL', default='postgresql://...')
        >>>     ]
        >>> )
    """

    def __init__(
        self,
        name: str,
        os_name: Optional[str] = None,
        default: JinjaTemplate = "",
        should_render: bool = True,
    ):
        if name in RESERVED_ENV_NAMES:
            raise ValueError(f"Forbidden input name: {name}")
        self.__name: str = name
        self.__os_name: str = os_name if os_name is not None else name
        self.__default: str = default
        self.__should_render: bool = should_render

    def get_name(self) -> str:
        """
        Retrieves the name of the environment variable.

        Returns:
            str: The name of the environment variable.
        """
        return self.__name

    def get_os_name(self) -> Optional[str]:
        """
        Retrieves the OS-specific name of the environment variable.

        Returns:
            Optional[str]: The OS-specific name of the environment variable.
        """
        return self.__os_name

    def get_default(self) -> str:
        """
        Retrieves the default value of the environment variable.

        Returns:
            str: The default value of the environment variable.
        """
        return self.__default

    def should_render(self) -> bool:
        """
        Determines whether the environment value should be rendered.

        Returns:
            bool: True if the environment value should be rendered, False otherwise.
        """
        return self.__should_render

    def get(self, prefix: str = "") -> str:
        """
        Retrieves the value of the environment variable, considering an optional prefix.

        Args:
            prefix (str): An optional prefix to distinguish different environments (e.g., 'DEV', 'PROD').

        Returns:
            str: The value of the environment variable, considering the prefix and default value.

        Examples:
            >>> from zrb import Env
            >>> import os
            >>> os.environ['DEV_SERVER'] = 'localhost'
            >>> os.environ['PROD_SERVER'] = 'example.com'
            >>> env = Env(name='HOST', os_name='SERVER', default='0.0.0.0')
            >>> print(env.get('DEV'))   # will show 'localhost'
            >>> print(env.get('PROD'))  # will show 'example.com'
            >>> print(env.get('STAG'))  # will show '0.0.0.0'
        """
        if self.__os_name == "":
            return self.__default
        prefixed_name = self.__get_prefixed_name(self.__os_name, prefix)
        if prefixed_name in os.environ and os.environ[prefixed_name] != "":
            return os.environ[prefixed_name]
        if self.__os_name in os.environ and os.environ[self.__os_name] != "":
            return os.environ[self.__os_name]
        return self.__default

    def __get_prefixed_name(self, name: str, prefix: str):
        """
        Constructs the prefixed name of the environment variable.

        This method is intended for internal use only.

        Args:
            name (str): The base name of the environment variable.
            prefix (str): The prefix to be added to the name.

        Returns:
            str: The prefixed name of the environment variable.
        """
        if prefix is None or prefix == "":
            return name
        return prefix + "_" + name

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        name = double_quote(self.__name)
        os_name = "None" if self.__os_name is None else double_quote(self.__os_name)
        default = double_quote(self.__default)
        return f"<{cls_name} {name} os_name={os_name} default={default}>"
