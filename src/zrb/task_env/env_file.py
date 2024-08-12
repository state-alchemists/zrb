from typing import Optional

from dotenv import dotenv_values

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.string.modification import double_quote
from zrb.helper.typecheck import typechecked
from zrb.task_env.constant import RESERVED_ENV_NAMES
from zrb.task_env.env import Env

logger.debug(colored("Loading zrb.task_env.env_file", attrs=["dark"]))

# flake8: noqa E501


@typechecked
class EnvFile:
    """
    Env is an interface for a Task to read and use OS Environment File.

    Under the hood, EnvFile creates list of Env based on its `path` property.

    Attributes:
        path (str): The path to the environment file.
        prefix (Optional[str]): An optional prefix to be applied to environment variables.
        should_render (bool): Flag to determine if the environment values should be rendered.

    Examples:
        >>> from zrb import EnvFile, Task
        >>> import os
        >>> CURRENT_DIR = os.dirname(__file__)
        >>> task = Task(
        >>>     name='task',
        >>>     env_files=[
        >>>         EnvFile(path=os.path.join(CURRENT_DIR, '.env'), prefix='SYSTEM')
        >>>     ]
        >>> )
    """

    def __init__(
        self, path: str, prefix: Optional[str] = None, should_render: bool = False
    ):
        self.__path = path
        self.__prefix = prefix.upper() if prefix is not None else None
        self.__should_render = should_render
        self.__env_list: list[Env] = []
        self.__env_list_fetched: bool = False

    def get_envs(self) -> list[Env]:
        """
        Retrieves a list of Env objects based on the environment file. If a prefix is provided, it is
        applied to the environment variable names.

        Returns:
            list[Env]: A list of Env objects representing the environment variables defined in the file.

        Examples:
            >>> from zrb import Env, EnvFile
            >>> env_file = EnvFile(path='some_file.env')
            >>> envs: list[Env] = env_file.get_envs()
        """
        if self.__env_list_fetched:
            return self.__env_list
        env_list: list[Env] = []
        env_map = dotenv_values(self.__path)
        for key, value in env_map.items():
            if key in RESERVED_ENV_NAMES:
                continue
            os_name: Optional[str] = None
            if self.__prefix is not None and self.__prefix != "":
                os_name = f"{self.__prefix}_{key}"
            env_list.append(
                Env(
                    name=key,
                    os_name=os_name,
                    default=value,
                    should_render=self.__should_render,
                )
            )
        self.__env_list = env_list
        self.__env_list_fetched = True
        return env_list

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        path = double_quote(self.__path)
        prefix = double_quote(self.__prefix)
        return f"<{cls_name} path={path} prefix={prefix}>"
