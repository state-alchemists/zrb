from typing import Any, Callable, Iterable, Mapping, Optional, Union
from typeguard import typechecked
from .base_task import BaseTask
from .cmd_task import CmdTask
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput
from ..task_group.group import Group
from ..helper.string.double_quote import double_quote
from ..helper.dockercompose.read import read_file as read_compose_file
from ..helper.dockercompose.fetch_external_env import fetch_external_env

import os
import pathlib


@typechecked
class DockerComposeTask(CmdTask):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        service_env_files: Mapping[str, Iterable[EnvFile]] = {},
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        executable: Optional[str] = None,
        compose_file: Optional[str] = None,
        compose_cmd: str = 'up',
        compose_options: Mapping[str, str] = {},
        compose_flags: Iterable[str] = [],
        compose_args: Iterable[str] = [],
        compose_env_prefix: str = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[BaseTask] = [],
        checkers: Iterable[BaseTask] = [],
        checking_interval: float = 0.1,
        retry: int = 2,
        retry_interval: float = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str] = False
    ):
        combined_env_files = list(env_files)
        for _, service_env_files in service_env_files.items():
            combined_env_files = combined_env_files + service_env_files
        CmdTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=combined_env_files,
            icon=icon,
            color=color,
            description=description,
            executable=executable,
            cwd=cwd,
            upstreams=upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            preexec_fn=preexec_fn,
            skip_execution=skip_execution
        )
        self.compose_cmd = compose_cmd
        self.compose_options = compose_options
        self.compose_flags = compose_flags
        self.compose_args = compose_args
        self.compose_env_prefix = compose_env_prefix
        self._set_compose_file(compose_file)
        self._fill_envs()

    def _fill_envs(self):
        data = read_compose_file(self.compose_file)
        env_map = fetch_external_env(data)
        for key, value in env_map.items():
            existing_env = [env for env in self.envs if env.name == key]
            if len(existing_env) > 0:
                # Don't override existing env
                continue
            os_name = key
            if self.compose_env_prefix != '':
                os_name = f'{self.compose_env_prefix}_{os_name}'
            self.envs.append(Env(name=key, os_name=os_name, default=value))

    def _set_compose_file(self, compose_file: Optional[str]):
        if compose_file is None:
            for _compose_file in [
                'compose.yml', 'compose.yaml',
                'docker-compose.yml', 'docker-compose.yaml'
            ]:
                if os.path.exists(os.path.join(self.cwd, _compose_file)):
                    self.compose_file: str = os.path.join(
                        self.cwd, _compose_file
                    )
                    return
        if os.path.isabs(compose_file) and os.path.exists(compose_file):
            self.compose_file: str = compose_file
            return
        if os.path.exists(os.path.join(self.cwd, compose_file)):
            self.compose_file: str = os.path.join(self.cwd, compose_file)
            return
        raise Exception(f'Invalid compose file: {compose_file}')

    def _get_cmd_str(self) -> str:
        command_options = dict(self.compose_options)
        if '--file' not in command_options and '-f' not in command_options:
            command_options['--file'] = self.compose_file
        options = ' '.join([
            f'{self.render_str(key)} {double_quote(self.render_str(val))}'
            for key, val in command_options.items()
        ])
        flags = ' '.join([
            self.render_str(flag) for flag in self.compose_flags
        ])
        args = ' '.join([
            double_quote(self.render_str(arg)) for arg in self.compose_args
        ])
        cmd = f'docker compose {options} {flags} {self.compose_cmd} {args}'
        self.log_info(f'Command: {cmd}')
        return cmd
