import os

from zrb.helper.accessories.color import get_random_color
from zrb.helper.accessories.icon import get_random_icon
from zrb.helper.string.conversion import to_cli_name
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import (
    Any,
    Callable,
    Iterable,
    JinjaTemplate,
    List,
    Mapping,
    Optional,
    Union,
)
from zrb.helper.util import coalesce_str
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
from zrb.task_env.constant import RESERVED_ENV_NAMES
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput


@typechecked
class CommonTaskModel:
    def __init__(
        self,
        name: str,
        group: Optional[Group] = None,
        description: str = "",
        inputs: List[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        retry: int = 2,
        retry_interval: Union[float, int] = 1,
        upstreams: Iterable[AnyTask] = [],
        checkers: Iterable[AnyTask] = [],
        checking_interval: Union[float, int] = 0,
        run: Optional[Callable[..., Any]] = None,
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        should_execute: Union[bool, JinjaTemplate, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
    ):
        self._name = name
        self._group = group
        if group is not None:
            group._add_task(self)
        self._description = coalesce_str(description, name)
        self._inputs = inputs
        self._envs = envs
        self._env_files = env_files
        self._icon = coalesce_str(icon, get_random_icon())
        self._color = coalesce_str(color, get_random_color())
        self._retry = retry
        self._retry_interval = retry_interval
        self._upstreams = upstreams
        self._checkers = [checker.copy() for checker in checkers]
        self._checking_interval = checking_interval
        self._run_function: Optional[Callable[..., Any]] = run
        self._on_triggered = on_triggered
        self._on_waiting = on_waiting
        self._on_skipped = on_skipped
        self._on_started = on_started
        self._on_ready = on_ready
        self._on_retry = on_retry
        self._on_failed = on_failed
        self._should_execute = should_execute
        self._return_upstream_result = return_upstream_result
        self.__execution_id = ""
        self.__allow_add_envs = True
        self.__allow_add_env_files = True
        self.__allow_add_inputs = True
        self.__allow_add_upstreams: bool = True
        self.__allow_add_checkers: bool = True
        self.__has_already_inject_env_files: bool = False
        self.__has_already_inject_envs: bool = False
        self.__has_already_inject_inputs: bool = False
        self.__has_already_inject_upstreams: bool = False
        self.__all_inputs: Optional[List[AnyInput]] = None

    def _lock_upstreams(self):
        self.__allow_add_upstreams = False

    def _set_execution_id(self, execution_id: str):
        if self.__execution_id == "":
            self.__execution_id = execution_id

    def _propagate_execution_id(self):
        execution_id = self.get_execution_id()
        for upstream_task in self._get_upstreams():
            upstream_task._set_execution_id(execution_id)
            upstream_task._propagate_execution_id()
        for checker_task in self._get_checkers():
            checker_task._set_execution_id(execution_id)
            checker_task._propagate_execution_id()

    def get_execution_id(self) -> str:
        return self.__execution_id

    def set_name(self, new_name: str):
        if self._description == self.get_name():
            self._description = new_name
        self._name = new_name

    def get_name(self) -> str:
        return self._name

    def get_cli_name(self) -> str:
        return to_cli_name(self.get_name())

    def set_description(self, new_description: str):
        self._description = new_description

    def get_description(self) -> str:
        return self._description

    def set_icon(self, new_icon: str):
        self._icon = new_icon

    def set_color(self, new_color: str):
        self._color = new_color

    def set_retry(self, new_retry: int):
        self._retry = new_retry

    def set_should_execute(
        self, should_execute: Union[bool, JinjaTemplate, Callable[..., bool]]
    ):
        self._should_execute = should_execute

    def set_retry_interval(self, new_retry_interval: Union[float, int]):
        self._retry_interval = new_retry_interval

    def set_checking_interval(self, new_checking_interval: Union[float, int]):
        self._checking_interval = new_checking_interval

    def insert_input(self, *inputs: AnyInput):
        if not self.__allow_add_inputs:
            raise Exception(f"Cannot insert inputs for `{self.get_name()}`")
        self._inputs = list(inputs) + list(self._inputs)

    def add_input(self, *inputs: AnyInput):
        if not self.__allow_add_inputs:
            raise Exception(f"Cannot add inputs for `{self.get_name()}`")
        self._inputs = list(self._inputs) + list(inputs)

    def inject_inputs(self):
        pass

    def _get_inputs(self) -> List[AnyInput]:
        if not self.__has_already_inject_inputs:
            self.inject_inputs()
            self.__has_already_inject_inputs = True
        return list(self._inputs)

    def _get_combined_inputs(self) -> Iterable[AnyInput]:
        """'
        Getting all inputs of this task and all its upstream, non-duplicated.
        """
        if self.__all_inputs is not None:
            return self.__all_inputs
        self.__all_inputs: List[AnyInput] = []
        existing_input_names: Mapping[str, bool] = {}
        # Add task inputs
        inputs = self._get_inputs()
        for input_index, first_occurence_task_input in enumerate(inputs):
            input_name = first_occurence_task_input.get_name()
            if input_name in existing_input_names:
                continue
            # Look for all input with the same name in the current task
            task_inputs = [
                candidate
                for candidate in inputs[input_index:]
                if candidate.get_name() == input_name
            ]
            # Get the last input, and add it to _all_inputs
            task_input = task_inputs[-1]
            self.__all_inputs.append(task_input)
            existing_input_names[input_name] = True
        # Add upstream inputs
        for upstream in self._get_upstreams():
            upstream_inputs = upstream._get_combined_inputs()
            for upstream_input in upstream_inputs:
                if upstream_input.get_name() in existing_input_names:
                    continue
                self.__all_inputs.append(upstream_input)
                existing_input_names[upstream_input.get_name()] = True
        self._lock_upstreams()
        self.__allow_add_inputs = False
        return self.__all_inputs

    def insert_env(self, *envs: Env):
        if not self.__allow_add_envs:
            raise Exception(f"Cannot insert envs to `{self.get_name()}`")
        self._envs = list(envs) + list(self._envs)

    def add_env(self, *envs: Env):
        if not self.__allow_add_envs:
            raise Exception(f"Cannot add envs to `{self.get_name()}`")
        self._envs = list(self._envs) + list(envs)

    def inject_envs(self):
        pass

    def _get_envs(self) -> List[Env]:
        if not self.__has_already_inject_envs:
            self.inject_envs()
            self.__has_already_inject_envs = True
        return list(self._envs)

    def _get_combined_env(self) -> Mapping[str, Env]:
        all_envs: Mapping[str, Env] = {}
        for env_name in os.environ:
            if env_name in RESERVED_ENV_NAMES:
                continue
            all_envs[env_name] = Env(
                name=env_name, os_name=env_name, should_render=False
            )
        for env_file in self._get_env_files():
            for env in env_file.get_envs():
                all_envs[env.get_name()] = env
        for env in self._get_envs():
            all_envs[env.get_name()] = env
        self.__allow_add_envs = False
        self.__allow_add_env_files = False
        return all_envs

    def insert_env_file(self, *env_files: EnvFile):
        if not self.__allow_add_env_files:
            raise Exception(f"Cannot insert env_files to `{self.get_name()}`")
        self._env_files = list(env_files) + list(self._env_files)

    def add_env_file(self, *env_files: EnvFile):
        if not self.__allow_add_env_files:
            raise Exception(f"Cannot add env_files to `{self.get_name()}`")
        self._env_files = list(self._env_files) + list(env_files)

    def inject_env_files(self):
        pass

    def insert_upstream(self, *upstreams: AnyTask):
        if not self.__allow_add_upstreams:
            raise Exception(f"Cannot insert upstreams to `{self.get_name()}`")
        self._upstreams = list(upstreams) + list(self._upstreams)

    def add_upstream(self, *upstreams: AnyTask):
        if not self.__allow_add_upstreams:
            raise Exception(f"Cannot add upstreams to `{self.get_name()}`")
        self._upstreams = list(self._upstreams) + list(upstreams)

    def inject_upstreams(self):
        pass

    def _get_upstreams(self) -> List[AnyTask]:
        if not self.__has_already_inject_upstreams:
            self.inject_upstreams()
            self.__has_already_inject_upstreams = True
        return list(self._upstreams)

    def get_icon(self) -> str:
        return self._icon

    def get_color(self) -> str:
        return self._color

    def _get_env_files(self) -> List[EnvFile]:
        if not self.__has_already_inject_env_files:
            self.inject_env_files()
            self.__has_already_inject_env_files = True
        return self._env_files

    def insert_checker(self, *checkers: AnyTask):
        if not self.__allow_add_checkers:
            raise Exception(f"Cannot insert checkers to `{self.get_name()}`")
        additional_checkers = [checker.copy() for checker in checkers]
        self._checkers = additional_checkers + self._checkers

    def add_checker(self, *checkers: AnyTask):
        if not self.__allow_add_checkers:
            raise Exception(f"Cannot add checkers to `{self.get_name()}`")
        additional_checkers = [checker.copy() for checker in checkers]
        self._checkers = self._checkers + additional_checkers

    def inject_checkers(self):
        pass

    def _get_checkers(self) -> List[AnyTask]:
        if not self.__allow_add_checkers:
            self.inject_checkers()
            self.__allow_add_checkers = True
        return self._checkers
