import os
import pathlib
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, Union

from zrb.helper.accessories.color import colored
from zrb.helper.docker_compose.file import read_local_compose_file, write_local_compose_file
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import JinjaTemplate
from zrb.helper.util import to_snake_case
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnFailed,
    OnReady,
    OnRetry,
    OnSkipped,
    OnStarted,
    OnTriggered,
    OnWaiting,
)
from zrb.task.base_task.base_task import BaseTask
from zrb.task.docker_compose_task import ServiceConfig
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.docker_compose_maker", attrs=["dark"]))


@typechecked
class DockerComposeMaker(BaseTask):
    def __init__(
        self,
        name: str,
        template_file: Optional[str] = None,
        compose_file: Optional[str] = None,
        compose_service_configs: Mapping[str, ServiceConfig] = {},
        cwd: Optional[Union[JinjaTemplate, pathlib.Path]] = None,
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        upstreams: Iterable[AnyTask] = [],
        fallbacks: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
    ):
        BaseTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            upstreams=upstreams,
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=[],
            checking_interval=0.05,
            retry=0,
            retry_interval=0,
            should_execute=should_execute,
        )
        self._cwd = os.getcwd() if cwd is None else os.path.abspath(cwd)
        self._template_file = self.__get_template_file(template_file)
        self._compose_file = self.__get_compose_file(compose_file)
        self._compose_service_configs = compose_service_configs

    def set_cwd(self, cwd: Optional[Union[JinjaTemplate, pathlib.Path]]):
        self._cwd = os.getcwd() if cwd is None else os.path.abspath(cwd)

    def _get_cwd(self) -> Union[str, pathlib.Path]:
        if self._should_render_cwd and isinstance(self._cwd, str):
            return self.render_str(self._cwd)
        return self._cwd

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self.print_out_dark(f"Reading from {self._compose_file}")
        compose_data = read_local_compose_file(self._template_file)
        for service, service_config in self._compose_service_configs.items():
            envs: list[Env] = []
            env_files = service_config.get_env_files()
            for env_file in env_files:
                envs += env_file.get_envs()
            envs += service_config.get_envs()
            compose_data = self.__apply_service_env(compose_data, service, envs)
        self.print_out_dark(f"Writing to {self._compose_file}")
        write_local_compose_file(self._compose_file, compose_data)
        return True

    def __apply_service_env(
        self, compose_data: Any, service_name: str, envs: list[Env]
    ) -> Any:
        # service not found
        service_map = compose_data["services"]
        if "services" not in compose_data or service_name not in service_map:
            self.log_error(f"Cannot find services.{service_name}")
            return compose_data
        # service has no environment definition
        if "environment" not in compose_data["services"][service_name]:
            compose_data["services"][service_name]["environment"] = {
                env.get_name(): self.__get_env_compose_value(service_name, env)
                for env in envs
            }
            return compose_data
        # service environment is a map
        if isinstance(compose_data["services"][service_name]["environment"], dict):
            new_env_map = self.__get_service_new_env_map(
                service_name=service_name,
                service_env_map=compose_data["services"][service_name]["environment"],
                new_envs=envs,
            )
            for key, value in new_env_map.items():
                compose_data["services"][service_name]["environment"][key] = value
            return compose_data
        # service environment is a list
        if isinstance(compose_data["services"][service_name]["environment"], list):
            new_env_list = self.__get_service_new_env_list(
                service_name=service_name,
                service_env_list=compose_data["services"][service_name]["environment"],
                new_envs=envs,
            )
            compose_data["services"][service_name]["environment"] += new_env_list
            return compose_data
        return compose_data

    def __get_service_new_env_map(
        self, service_name: str, service_env_map: Mapping[str, str], new_envs: list[Env]
    ) -> Mapping[str, str]:
        new_service_envs: Mapping[str, str] = {}
        for env in new_envs:
            env_name = env.get_name()
            if env_name in service_env_map:
                continue
            new_service_envs[env_name] = self.__get_env_compose_value(service_name, env)
        return new_service_envs

    def __get_service_new_env_list(
        self, service_name: str, service_env_list: list[str], new_envs: list[Env]
    ) -> list[str]:
        new_service_envs: list[str] = []
        for env in new_envs:
            should_be_added = 0 == len(
                [
                    service_env
                    for service_env in service_env_list
                    if service_env.startswith(env.get_name() + "=")
                ]
            )
            if not should_be_added:
                continue
            new_service_envs.append(
                env.get_name() + "=" + self.__get_env_compose_value(service_name, env)
            )
        return new_service_envs

    def __get_env_compose_value(self, service_name: str, env: Env) -> str:
        env_prefix = to_snake_case(service_name).upper()
        env_name = env.get_name()
        env_default = env.get_default()
        return f"${{{env_prefix}_{env_name}:-{env_default}}}"

    def __get_template_file(self, template_file: Optional[str]) -> str:
        if template_file is None:
            for name in ["compose", "docker-compose"]:
                for tpl in ["template", "tpl"]:
                    for ext in ["yaml", "yml"]:
                        template_file = os.path.join(self._cwd, f"{name}.{tpl}.{ext}")
                        if os.path.exists(template_file):
                            return template_file
            raise Exception(f"Cannot find template file on {self._cwd}")
        if os.path.isabs(template_file) and os.path.exists(template_file):
            return template_file
        if os.path.exists(os.path.join(self._cwd, template_file)):
            return os.path.join(self._cwd, template_file)
        raise Exception(f"Invalid template file: {template_file}")

    def __get_compose_file(self, compose_file: Optional[str]) -> str:
        if compose_file is None:
            for name in ["compose", "docker-compose"]:
                for tpl in ["template", "tpl"]:
                    for ext in ["yaml", "yml"]:
                        template_file = os.path.join(self._cwd, f"{name}.{tpl}.{ext}")
                        if os.path.exists(template_file):
                            return os.path.join(self._cwd, f"{name}.{ext}")
            return os.path.join(self._cwd, "docker-compose.yaml")
        if os.path.isabs(compose_file):
            return compose_file
        else:
            return os.path.join(self._cwd, compose_file)
