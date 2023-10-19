from zrb.helper.typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Union, TypeVar
)
from abc import ABC, abstractmethod
from zrb.task_env.env_file import EnvFile
from zrb.task_env.env import Env
from zrb.task_input.any_input import AnyInput

TAnyTask = TypeVar('TAnyTask', bound='AnyTask')


class AnyTask(ABC):
    '''
    Task class specification.
    In order to create a new Task class, you have to implements all methods.
    You can do this by extending BaseTask.

    Currently we don't see any advantage to break this interface into
    multiple interfaces since AnyTask is considered atomic.
    '''
    @abstractmethod
    def copy(self) -> TAnyTask:
        pass

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    async def check(self) -> bool:
        pass

    @abstractmethod
    def to_function(
        self, env_prefix: str = '', raise_error: bool = True
    ) -> Callable[..., Any]:
        pass

    @abstractmethod
    def add_upstreams(self, *upstreams: TAnyTask):
        pass

    @abstractmethod
    def add_inputs(self, *inputs: AnyInput):
        pass

    @abstractmethod
    def add_envs(self, *envs: Env):
        pass

    @abstractmethod
    def add_env_files(self, *env_files: EnvFile):
        pass

    @abstractmethod
    def set_name(self, new_name: str):
        pass

    @abstractmethod
    def set_description(self, new_description: str):
        pass

    @abstractmethod
    def set_icon(self, new_icon: str):
        pass

    @abstractmethod
    def set_color(self, new_color: str):
        pass

    @abstractmethod
    def set_should_execute(
        self, should_execute: Union[bool, str, Callable[..., bool]]
    ):
        pass

    @abstractmethod
    def set_retry(self, new_retry: int):
        pass

    @abstractmethod
    def set_retry_interval(self, new_retry_interval: Union[float, int]):
        pass

    @abstractmethod
    def set_checking_interval(self, new_checking_interval: Union[float, int]):
        pass

    @abstractmethod
    def get_icon(self) -> str:
        pass

    @abstractmethod
    def get_color(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_cmd_name(self) -> str:
        pass

    @abstractmethod
    def get_env_files(self) -> List[EnvFile]:
        pass

    @abstractmethod
    def get_envs(self) -> List[Env]:
        pass

    @abstractmethod
    def get_inputs(self) -> List[AnyInput]:
        pass

    @abstractmethod
    def get_checkers(self) -> Iterable[TAnyTask]:
        pass

    @abstractmethod
    def get_upstreams(self) -> Iterable[TAnyTask]:
        pass

    @abstractmethod
    def get_all_inputs(self) -> Iterable[AnyInput]:
        pass

    @abstractmethod
    def log_debug(self, message: Any):
        pass

    @abstractmethod
    def log_warn(self, message: Any):
        pass

    @abstractmethod
    def log_info(self, message: Any):
        pass

    @abstractmethod
    def log_error(self, message: Any):
        pass

    @abstractmethod
    def log_critical(self, message: Any):
        pass

    @abstractmethod
    def print_out(self, message: Any, trim_message: bool = True):
        pass

    @abstractmethod
    def print_err(self, message: Any, trim_message: bool = True):
        pass

    @abstractmethod
    def print_out_dark(self, message: Any, trim_message: bool = True):
        pass

    @abstractmethod
    def get_input_map(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def get_env_map(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def inject_env_map(
        self, env_map: Mapping[str, str], override: bool = False
    ):
        pass

    @abstractmethod
    def render_any(
        self, val: Any, data: Optional[Mapping[str, Any]] = None
    ) -> Any:
        pass

    @abstractmethod
    def render_float(
        self, val: Union[str, float], data: Optional[Mapping[str, Any]] = None
    ) -> float:
        pass

    @abstractmethod
    def render_int(
        self, val: Union[str, int], data: Optional[Mapping[str, Any]] = None
    ) -> int:
        pass

    @abstractmethod
    def render_bool(
        self, val: Union[str, bool], data: Optional[Mapping[str, Any]] = None
    ) -> bool:
        pass

    @abstractmethod
    def render_str(
        self, val: str, data: Optional[Mapping[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def render_file(
        self, location: str, data: Optional[Mapping[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def _run_all(self, *args: Any, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    def _loop_check(self, show_info: bool) -> bool:
        pass

    @abstractmethod
    def _set_keyval(self, kwargs: Mapping[str, Any], env_prefix: str):
        pass

    @abstractmethod
    def _print_result(self, result: Any):
        pass

    @abstractmethod
    def print_result(self, result: Any):
        pass
