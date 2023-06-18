from typing import Any, Callable, Iterable, List, Mapping, Optional, Union
from typeguard import typechecked
from .base_task import BaseTask, Group
from .cmd_task import CmdTask, CmdResult
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput
from ..helper.string.double_quote import double_quote
from ..helper.docker_compose.file import read_compose_file, write_compose_file
from ..helper.docker_compose.fetch_external_env import (
    fetch_compose_file_env_map
)

import os
import pathlib


@typechecked
class ServiceConfig():
    def __init__(self, envs: List[Env] = [], env_files: List[EnvFile] = []):
        self._envs = envs
        self._env_files = env_files

    def get_envs(self) -> List[Env]:
        return self._envs

    def get_env_files(self) -> List[EnvFile]:
        return self._env_files


@typechecked
class DockerComposeTask(CmdTask):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        executable: Optional[str] = None,
        compose_service_configs: Mapping[str, ServiceConfig] = {},
        compose_file: Optional[str] = None,
        compose_cmd: str = 'up',
        compose_options: Mapping[str, str] = {},
        compose_flags: Iterable[str] = [],
        compose_args: Iterable[str] = [],
        compose_env_prefix: str = '',
        setup_cmd: Union[str, Iterable[str]] = '',
        setup_cmd_path: str = '',
        cwd: Optional[Union[str, pathlib.Path]] = None,
        upstreams: Iterable[BaseTask] = [],
        checkers: Iterable[BaseTask] = [],
        checking_interval: float = 0.1,
        retry: int = 2,
        retry_interval: float = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
        combined_env_files = list(env_files)
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
        self._setup_cmd = setup_cmd
        self._setup_cmd_path = setup_cmd_path
        self._compose_service_configs = compose_service_configs
        self._compose_cmd = compose_cmd
        self._compose_options = compose_options
        if '--f' in compose_options:
            raise ValueError('compose option cannot contains --f')
        if '--file' in compose_options:
            raise ValueError('compose option cannot contains --file')
        self._compose_flags = compose_flags
        self._compose_args = compose_args
        self._compose_env_prefix = compose_env_prefix
        self._compose_template_file = self._get_compose_template_file(
            compose_file
        )
        self._compose_runtime_file = self._get_compose_runtime_file(
            self._compose_template_file
        )
        # append services env and env_files to current task
        for _, service_config in self._compose_service_configs.items():
            self._env_files += service_config.get_env_files()
            self._envs += service_config.get_envs()
        self._add_compose_envs()

    async def run(self, *args, **kwargs: Any) -> CmdResult:
        self._generate_compose_runtime_file()
        return await super().run(*args, **kwargs)

    def _generate_compose_runtime_file(self):
        compose_data = read_compose_file(self._compose_template_file)
        for service, service_config in self._compose_service_configs.items():
            envs = service_config.get_envs()
            env_files = service_config.get_env_files()
            for env_file in env_files:
                envs += env_file.get_envs()
            compose_data = self._add_service_env(compose_data, service, envs)
        write_compose_file(self._compose_runtime_file, compose_data)

    def _add_service_env(
        self, compose_data: Any, service: str, envs: List[Env]
    ) -> Any:
        # service not found
        if 'services' not in compose_data or service not in compose_data['services']: # noqa
            return compose_data
        # service has no environment definition
        if 'environment' not in compose_data['services'][service]:
            compose_data['services'][service]['environment'] = {
                env.name: self._get_env_compose_value(env) for env in envs
            }
            return compose_data
        # service environment is a map
        if isinstance(compose_data['services'][service]['environment'], dict):
            new_env_map = self._get_service_new_env_map(
                compose_data['services'][service]['environment'], envs
            )
            for key, value in new_env_map.items():
                compose_data['services'][service]['environment'][key] = value
            return compose_data
        # service environment is a list
        if isinstance(compose_data['services'][service]['environment'], list):
            new_env_list = self._get_service_new_env_list(
                compose_data['services'][service]['environment'], envs
            )
            compose_data['services'][service]['environment'] += new_env_list
            return compose_data
        return compose_data

    def _get_service_new_env_map(
        self, service_env_map: Mapping[str, str], new_envs: List[Env]
    ) -> Mapping[str, str]:
        new_service_envs: Mapping[str, str] = {}
        for env in new_envs:
            if env.name in service_env_map:
                continue
            new_service_envs[env.name] = self._get_env_compose_value(env)
        return new_service_envs

    def _get_service_new_env_list(
        self, service_env_list: List[str], new_envs: List[Env]
    ) -> List[str]:
        new_service_envs: List[str] = []
        for env in new_envs:
            should_be_added = 0 == len([
                service_env for service_env in service_env_list
                if service_env.startswith(env.name + '=')
            ])
            if not should_be_added:
                continue
            new_service_envs.append(
                env.name + '=' + self._get_env_compose_value(env)
            )
        return new_service_envs

    def _get_env_compose_value(self, env: Env) -> str:
        return '${' + env.name + ':-' + env.default + '}'

    def _add_compose_envs(self):
        data = read_compose_file(self._compose_template_file)
        env_map = fetch_compose_file_env_map(data)
        for key, value in env_map.items():
            # Need to get this everytime because we only want
            # the first compose file env value for a certain key
            existing_env_map = self._get_existing_env_map()
            if key in existing_env_map:
                continue
            os_name = key
            if self._compose_env_prefix != '':
                os_name = f'{self._compose_env_prefix}_{os_name}'
            self._envs.append(Env(name=key, os_name=os_name, default=value))

    def _get_existing_env_map(self) -> Mapping[str, str]:
        env_map: Mapping[str, str] = {}
        for env_file in self._env_files:
            envs = env_file.get_envs()
            env_map.update({
                env.name: env.default for env in envs
            })
        env_map.update({
            env.name: env.default for env in self._envs
        })
        return env_map

    def _get_compose_runtime_file(self, compose_file_name: str) -> str:
        directory, file = os.path.split(compose_file_name)
        prefix = '_' if file.startswith('.') else '._'
        file_parts = file.split('.')
        if len(file_parts) > 1:
            file_parts[-2] += '.runtime'
            runtime_file_name = prefix + '.'.join(file_parts)
            return os.path.join(directory, runtime_file_name)
        runtime_file_name = prefix + file + '.runtime'
        return os.path.join(directory, runtime_file_name)

    def _get_compose_template_file(self, compose_file: Optional[str]) -> str:
        if compose_file is None:
            for _compose_file in [
                'compose.yml', 'compose.yaml',
                'docker-compose.yml', 'docker-compose.yaml'
            ]:
                if os.path.exists(os.path.join(self.cwd, _compose_file)):
                    return os.path.join(self.cwd, _compose_file)
                    return
            raise Exception(f'Cannot find compose file on {self.cwd}')
        if os.path.isabs(compose_file) and os.path.exists(compose_file):
            return compose_file
        if os.path.exists(os.path.join(self.cwd, compose_file)):
            return os.path.join(self.cwd, compose_file)
        raise Exception(f'Invalid compose file: {compose_file}')

    def _get_cmd_str(self) -> str:
        setup_cmd_str = self._create_cmd_str(
            self._setup_cmd_path, self._setup_cmd
        )
        command_options = dict(self._compose_options)
        command_options['--file'] = self._compose_runtime_file
        options = ' '.join([
            f'{self.render_str(key)} {double_quote(self.render_str(val))}'
            for key, val in command_options.items()
            if self.render_str(val) != ''
        ])
        flags = ' '.join([
            self.render_str(flag) for flag in self._compose_flags
            if self.render_str(flag) != ''
        ])
        args = ' '.join([
            double_quote(self.render_str(arg)) for arg in self._compose_args
            if self.render_str(arg) != ''
        ])
        cmd_str = '\n'.join([
            setup_cmd_str,
            f'docker compose {options} {self._compose_cmd} {flags} {args}',
        ])
        self.log_info(f'Command: {cmd_str}')
        return cmd_str