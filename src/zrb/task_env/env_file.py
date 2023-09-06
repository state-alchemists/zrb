from zrb.helper.typing import List, Optional
from zrb.helper.typecheck import typechecked
from dotenv import dotenv_values
from zrb.task_env.env import Env


@typechecked
class EnvFile():

    def __init__(
        self,
        env_file: str,
        prefix: Optional[str] = None,
        renderable: bool = False
    ):
        self.env_file = env_file
        self.prefix = prefix.upper() if prefix is not None else None
        self.renderable = renderable
        self._env_list: List[Env] = []
        self._env_list_fetched: bool = False

    def get_envs(self) -> List[Env]:
        if self._env_list_fetched:
            return self._env_list
        env_list: List[Env] = []
        env_map = dotenv_values(self.env_file)
        for key, value in env_map.items():
            os_name: Optional[str] = None
            if self.prefix is not None and self.prefix != '':
                os_name = f'{self.prefix}_{key}'
            env_list.append(Env(
                name=key,
                os_name=os_name,
                default=value,
                renderable=self.renderable
            ))
        self._env_list = env_list
        self._env_list_fetched = True
        return env_list

    def __repr__(self) -> str:
        env_file = self.env_file
        prefix = self.prefix
        return f'<EnvFile file={env_file} prefix={prefix}>'
