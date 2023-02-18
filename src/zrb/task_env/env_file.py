from typing import List
from typeguard import typechecked
from dotenv import dotenv_values
from .env import Env


@typechecked
class EnvFile():

    def __init__(self, env_file: str, prefix: str = ''):
        self.env_file = env_file
        self.prefix = prefix.upper()

    def get_envs(self) -> List[Env]:
        envs: List[Env] = []
        env_map = dotenv_values(self.env_file)
        for key, value in env_map.items():
            os_name = key
            if self.prefix != '':
                os_name = f'{self.prefix}_{os_name}'
            envs.append(Env(name=key, os_name=os_name, default=value))
        return envs
