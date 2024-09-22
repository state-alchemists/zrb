import os
import pathlib
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional, TypeVar, Union

from zrb.helper.accessories.color import colored
from zrb.helper.accessories.name import get_random_name
from zrb.helper.docker_compose.fetch_external_env import fetch_compose_file_env_map
from zrb.helper.docker_compose.file import read_compose_file, write_compose_file
from zrb.helper.log import logger
from zrb.helper.string.conversion import to_cli_name
from zrb.helper.string.modification import double_quote
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
from zrb.task.cmd_task import CmdResult, CmdTask, CmdVal
from zrb.task_env.constant import RESERVED_ENV_NAMES
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.docker_compose_task", attrs=["dark"]))

TDockerComposeTask = TypeVar("TDockerComposeTask", bound="DockerComposeTask")

CURRENT_DIR = os.path.dirname(__file__)
SHELL_SCRIPT_DIR = os.path.join(CURRENT_DIR, "..", "shell-scripts")

ensure_container_backend = CmdTask(
    name="ensure-compose-backend",
    cmd_path=[
        os.path.join(SHELL_SCRIPT_DIR, "_common-util.sh"),
        os.path.join(SHELL_SCRIPT_DIR, "ensure-docker-is-installed.sh"),
    ],
    preexec_fn=None,
    should_print_cmd_result=False,
    should_show_cmd=False,
    should_show_working_directory=False,
)


@typechecked
class ServiceConfig:
    def __init__(self, envs: list[Env] = [], env_files: list[EnvFile] = []):
        self._envs = envs
        self._env_files = env_files

    def get_envs(self) -> list[Env]:
        return self._envs

    def get_env_files(self) -> list[EnvFile]:
        return self._env_files


@typechecked
class DockerComposeTask(CmdTask):
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = "",
        executable: Optional[str] = None,
        compose_service_configs: Mapping[str, ServiceConfig] = {},
        compose_file: Optional[str] = None,
        compose_cmd: str = "up",
        compose_options: Mapping[JinjaTemplate, JinjaTemplate] = {},
        compose_flags: Iterable[JinjaTemplate] = [],
        compose_args: Iterable[JinjaTemplate] = [],
        compose_profiles: CmdVal = "",
        compose_env_prefix: str = "",
        setup_cmd: CmdVal = "",
        setup_cmd_path: CmdVal = "",
        cwd: Optional[Union[JinjaTemplate, pathlib.Path]] = None,
        should_render_cwd: bool = True,
        upstreams: Iterable[AnyTask] = [],
        fallbacks: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0.05,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        max_output_line: int = 1000,
        max_error_line: int = 1000,
        preexec_fn: Optional[Callable[[], Any]] = os.setsid,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
        should_print_cmd_result: bool = True,
        should_show_cmd: bool = True,
        should_show_working_directory: bool = True,
    ):
        CmdTask.__init__(
            self,
            name=name,
            group=group,
            inputs=inputs,
            envs=envs,
            env_files=env_files,
            icon=icon,
            color=color,
            description=description,
            executable=executable,
            cwd=cwd,
            should_render_cwd=should_render_cwd,
            upstreams=[ensure_container_backend] + upstreams,
            fallbacks=fallbacks,
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            max_output_line=max_output_line,
            max_error_line=max_error_line,
            preexec_fn=preexec_fn,
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
            should_print_cmd_result=should_print_cmd_result,
            should_show_cmd=should_show_cmd,
            should_show_working_directory=should_show_working_directory,
        )
        self._setup_cmd = setup_cmd
        self._setup_cmd_path = setup_cmd_path
        self._compose_service_configs = compose_service_configs
        self._compose_cmd = compose_cmd
        self._compose_options = compose_options
        if "--f" in compose_options:
            raise ValueError("compose option cannot contains --f")
        if "--file" in compose_options:
            raise ValueError("compose option cannot contains --file")
        self._compose_flags = compose_flags
        self._compose_args = compose_args
        self._compose_env_prefix = compose_env_prefix
        self._compose_profiles = compose_profiles
        self._compose_template_file = self.__get_compose_template_file(compose_file)
        self._compose_runtime_file = self.__get_compose_runtime_file(
            self._compose_template_file
        )
        # Flag to make mark whether service config and compose environments
        # has been added to this task's envs and env_files
        self._is_compose_additional_env_added = False
        self._is_compose_additional_env_file_added = False

    def copy(self) -> TDockerComposeTask:
        return super().copy()

    async def run(self, *args, **kwargs: Any) -> CmdResult:
        self.__generate_compose_runtime_file()
        try:
            result = await super().run(*args, **kwargs)
        finally:
            os.remove(self._compose_runtime_file)
        return result

    def inject_envs(self):
        super().inject_envs()
        # inject envs from service_configs
        for _, service_config in self._compose_service_configs.items():
            self.insert_env(*service_config.get_envs())
        # inject envs from docker compose file
        compose_data = read_compose_file(self._compose_template_file)
        env_map = fetch_compose_file_env_map(compose_data)
        added_env_map: Mapping[str, bool] = {}
        for key, value in env_map.items():
            # Need to get this everytime because we only want
            # the first compose file env value for a certain key
            if key in RESERVED_ENV_NAMES or key in added_env_map:
                continue
            added_env_map[key] = True
            os_name = key
            if self._compose_env_prefix != "":
                os_name = f"{self._compose_env_prefix}_{os_name}"
            self.insert_env(Env(name=key, os_name=os_name, default=value))

    def inject_env_files(self):
        # inject env_files from service_configs
        for _, service_config in self._compose_service_configs.items():
            self.insert_env_file(*service_config.get_env_files())

    def __generate_compose_runtime_file(self):
        compose_data = read_compose_file(self._compose_template_file)
        for service, service_config in self._compose_service_configs.items():
            envs: list[Env] = []
            env_files = service_config.get_env_files()
            for env_file in env_files:
                envs += env_file.get_envs()
            envs += service_config.get_envs()
            compose_data = self.__apply_service_env(compose_data, service, envs)
        write_compose_file(self._compose_runtime_file, compose_data)

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
        return "".join(["${", f"{env_prefix}_{env_name}:-{env_default}", "}"])

    def __get_compose_runtime_file(self, compose_file_name: str) -> str:
        directory, file = os.path.split(compose_file_name)
        prefix = "_" if file.startswith(".") else "._"
        runtime_prefix = self.get_cli_name()
        if self._group is not None:
            group_prefix = to_cli_name(self._group._get_full_cli_name())
            runtime_prefix = f"{group_prefix}-{runtime_prefix}"
        runtime_prefix += "-" + get_random_name(
            separator="-", add_random_digit=True, digit_count=3
        )
        runtime_prefix = "." + runtime_prefix + ".runtime"
        file_parts = file.split(".")
        if len(file_parts) > 1:
            file_parts[-2] += runtime_prefix
            runtime_file_name = prefix + ".".join(file_parts)
            return os.path.join(directory, runtime_file_name)
        runtime_file_name = prefix + file + runtime_prefix
        return os.path.join(directory, runtime_file_name)

    def __get_compose_template_file(self, compose_file: Optional[str]) -> str:
        if compose_file is None:
            for _compose_file in [
                "compose.yml",
                "compose.yaml",
                "docker-compose.yml",
                "docker-compose.yaml",
            ]:
                if os.path.exists(os.path.join(self._cwd, _compose_file)):
                    return os.path.join(self._cwd, _compose_file)
            raise Exception(f"Cannot find compose file on {self._cwd}")
        if os.path.isabs(compose_file) and os.path.exists(compose_file):
            return compose_file
        if os.path.exists(os.path.join(self._cwd, compose_file)):
            return os.path.join(self._cwd, compose_file)
        raise Exception(f"Invalid compose file: {compose_file}")

    def get_cmd_script(self, *args: Any, **kwargs: Any) -> str:
        cmd_list = []
        # create network
        create_network_script = self._get_create_compose_network_script()
        if create_network_script.strip() != "":
            cmd_list.append(create_network_script)
        # set compose profiles
        compose_profile_script = self._get_compose_profile_script(*args, **kwargs)
        if compose_profile_script.strip() != "":
            cmd_list.append(compose_profile_script)
        # setup
        setup_script = self._create_cmd_script(
            self._setup_cmd_path, self._setup_cmd, *args, **kwargs
        )
        if setup_script.strip() != "":
            cmd_list.append(setup_script)
        # compose command
        cmd_list.append(
            self._get_execute_docker_compose_script(
                compose_cmd=self._compose_cmd,
                compose_options=self._compose_options,
                compose_flags=self._compose_flags,
                compose_args=self._compose_args,
                *args,
            )
        )
        cmd_str = "\n".join(cmd_list)
        self.log_info(f"Command: {cmd_str}")
        return cmd_str

    def _get_compose_profile_script(self, *args, **kwargs) -> str:
        # Get list representation of self._compose_profiles
        compose_profiles = self._compose_profiles
        if callable(compose_profiles):
            compose_profiles = self._compose_profiles(*args, **kwargs)
        if isinstance(compose_profiles, str):
            compose_profiles = compose_profiles.split(",")
        # Get only non empty profiles
        filtered_compose_profiles = [
            self.render_str(profile)
            for profile in compose_profiles
            if self.render_str(profile).strip() != ""
        ]
        if len(filtered_compose_profiles) == 0:
            return ""
        compose_profiles_str = ",".join(filtered_compose_profiles)
        return f"export COMPOSE_PROFILES={compose_profiles_str}"

    def _get_create_compose_network_script(self) -> str:
        compose_data = read_compose_file(self._compose_runtime_file)
        networks: Mapping[str, Mapping[str, Any]] = compose_data.get("networks", {})
        scripts = []
        for key, config in networks.items():
            if not config.get("external", False):
                continue
            network_name = config.get("name", key)
            scripts.append(
                f"docker network inspect {network_name} > /dev/null 2>&1 || docker network create -d bridge{network_name}"  # noqa
            )
        return "\n".join(scripts)

    def _get_execute_docker_compose_script(
        self,
        compose_cmd: str,
        compose_options: Mapping[JinjaTemplate, JinjaTemplate],
        compose_flags: Iterable[JinjaTemplate],
        compose_args: Iterable[JinjaTemplate],
        *args: Any,
    ) -> str:
        command_options = dict(compose_options)
        command_options["--file"] = self._compose_runtime_file
        options = " ".join(
            [
                f"{self.render_str(key)} {double_quote(self.render_str(val))}"
                for key, val in command_options.items()
                if self.render_str(val) != ""
            ]
        )
        flags = " ".join(
            [
                self.render_str(flag)
                for flag in compose_flags
                if self.render_str(flag) != ""
            ]
        )
        args = " ".join(
            [
                double_quote(self.render_str(arg))
                for arg in compose_args
                if self.render_str(arg) != ""
            ]
        )
        return f"docker compose {options} {compose_cmd} {flags} {args}"
