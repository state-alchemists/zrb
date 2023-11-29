from zrb.helper.typing import List, Optional
from zrb.helper.typecheck import typechecked
from dotenv import dotenv_values
from zrb.task_env.constant import RESERVED_ENV_NAMES
from zrb.task_env.env import Env


@typechecked
class EnvFile():

    def __init__(
        self,
        env_file: str,
        prefix: Optional[str] = None,
        should_render: bool = False
    ):
        self.__env_file = env_file
        self.__prefix = prefix.upper() if prefix is not None else None
        self.__should_render = should_render
        self.__env_list: List[Env] = []
        self.__env_list_fetched: bool = False

    def get_envs(self) -> List[Env]:
        if self.__env_list_fetched:
            return self.__env_list
        env_list: List[Env] = []
        env_map = dotenv_values(self.__env_file)
        for key, value in env_map.items():
            if key in RESERVED_ENV_NAMES:
                continue
            os_name: Optional[str] = None
            if self.__prefix is not None and self.__prefix != '':
                os_name = f'{self.__prefix}_{key}'
            env_list.append(Env(
                name=key,
                os_name=os_name,
                default=value,
                should_render=self.__should_render
            ))
        self.__env_list = env_list
        self.__env_list_fetched = True
        return env_list

    def __repr__(self) -> str:
        env_file = self.__env_file
        prefix = self.__prefix
        return f'<EnvFile file={env_file} prefix={prefix}>'
