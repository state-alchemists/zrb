from typing import List, Optional
from typeguard import typechecked
from dotenv import dotenv_values
from .env import Env


@typechecked
class EnvFile():

    def __init__(self, env_file: str, prefix: Optional[str] = None):
        self.env_file = env_file
        self.prefix = prefix.upper() if prefix is not None else None

    def get_envs(self) -> List[Env]:
        envs: List[Env] = []
        env_map = dotenv_values(self.env_file)
        for key, value in env_map.items():
            os_name: Optional[str] = None
            if self.prefix is not None and self.prefix != '':
                os_name = f'{self.prefix}_{key}'
            envs.append(Env(name=key, os_name=os_name, default=value))
        return envs
