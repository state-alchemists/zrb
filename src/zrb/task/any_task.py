from zrb.helper.typing import (
    Any, Callable, Iterable, JinjaTemplate, List, Mapping, Optional, Union, TypeVar
)
from abc import ABC, abstractmethod
from zrb.task_env.env_file import EnvFile
from zrb.task_env.env import Env
from zrb.task_input.any_input import AnyInput

# flake8: noqa
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
        '''
        ## Description
        Return copy of the current task.

        You can change properties of the copied task using any of these methods:
        - `set_name`
        - `set_description`
        - `set_icon`
        - `set_color`
        - `add_upstream`
        - `insert_upstream`
        - `add_input`
        - `insert_input`
        - `add_env`
        - `insert_env`
        - `add_env_file`
        - `insert_env_file`
        - or any other methods depending on the TaskClass you use.

        ## Example

        ```python
        task = Task(name='my-task', cmd='echo hello')

        copied_task = task.copy()
        copied_task.set_name('new_name')
        ```
        '''
        pass

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        '''
        ## Description

        Define what to do when current task is started.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def run(self, *args: Any, **kwargs: Any) -> int:
                self.print_out('Doing some calculation')
                return 42
        ```
        '''
        pass

    @abstractmethod
    async def check(self) -> bool:
        '''
        ## Description
        
        Define how Zrb consider current task to be ready.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def run(self, *args: Any, **kwargs: Any) -> int:
                self.print_out('Doing some calculation')
                self._done = True
                return 42
            
            async def check(self) -> bool:
                # When self._done is True, consider the task to be "ready"
                return self._done is not None and self._done
        ```
        '''
        pass

    @abstractmethod
    async def on_triggered(self):
        '''
        ## Description

        Define what to do when the current task status is `triggered`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_triggered(self):
                self.print_out('The task has been triggered')
        ```
        '''
        pass

    @abstractmethod
    async def on_waiting(self):
        '''
        ## Description

        Define what to do when the current task status is `waiting`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_waiting(self):
                self.print_out('The task is waiting to be started')
        ```
        '''
        pass

    @abstractmethod
    async def on_skipped(self):
        '''
        ## Description

        Define what to do when the current task status is `skipped`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_skipped(self):
                self.print_out('The task is not started')
        ```
        '''
        pass

    @abstractmethod
    async def on_started(self):
        '''
        ## Description

        Define what to do when the current task status is `started`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_started(self):
                self.print_out('The task is started')
        ```
        '''
        pass

    @abstractmethod
    async def on_ready(self):
        '''
        ## Description

        Define what to do when the current task status is `ready`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_ready(self):
                self.print_out('The task is ready')
        ```
        '''
        pass

    @abstractmethod
    async def on_failed(self, is_last_attempt: bool, exception: Exception):
        '''
        ## Description

        Define what to do when the current task status is `failed`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_failed(self, is_last_attempt: bool, exception: Exception):
                if is_last_attempt:
                    self.print_out('The task is failed, and there will be no retry')
                    raise exception
                self.print_out('The task is failed, going to retry')
        ```
        '''
        pass

    @abstractmethod
    async def on_retry(self):
        '''
        ## Description

        Define what to do when the current task status is `retry`.

        You can override this method.

        ## Example

        ```python
        class MyTask(Task):
            async def on_retry(self):
                self.print_out('The task is retrying')
        ```
        '''
        pass

    @abstractmethod
    def to_function(
        self,
        env_prefix: str = '',
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True
    ) -> Callable[..., Any]:
        '''
        Turn current task into a callable.
        '''
        pass

    @abstractmethod
    def insert_upstream(self, *upstreams: TAnyTask):
        '''
        Insert AnyTask to the beginning of the current task's upstream list.
        '''
        pass

    @abstractmethod
    def add_upstream(self, *upstreams: TAnyTask):
        '''
        Add AnyTask to the end of the current task's upstream list.
        '''
        pass

    @abstractmethod
    def insert_input(self, *inputs: AnyInput):
        '''
        Insert AnyInput to the beginning of the current task's input list.
        If there are two input with the same name, the later will override the first ones.
        '''
        pass

    @abstractmethod
    def add_input(self, *inputs: AnyInput):
        '''
        Add AnyInput to the end of the current task's input list.
        If there are two input with the same name, the later will override the first ones.
        '''
        pass

    @abstractmethod
    def insert_env(self, *envs: Env):
        '''
        Insert Env to the beginning of the current task's env list.
        If there are two Env with the same name, the later will override the first ones.
        '''
        pass

    @abstractmethod
    def add_env(self, *envs: Env):
        '''
        Add Env to the end of the current task's env list.
        If there are two Env with the same name, the later will override the first ones.
        '''
        pass

    @abstractmethod
    def insert_env_file(self, *env_files: EnvFile):
        '''
        Insert EnvFile to the beginning of the current task's env_file list.
        If there are two EnvFile with the same name, the later will override the first ones.
        '''
        pass

    @abstractmethod
    def add_env_file(self, *env_files: EnvFile):
        '''
        Add EnvFile to the end of current task's env_file list.
        If there are two EnvFile with the same name, the later will override the first ones.
        '''
        pass

    @abstractmethod
    def _set_execution_id(self, execution_id: str):
        '''
        Set current task execution id.
        
        This method is meant for internal use.
        '''
        pass

    @abstractmethod
    def set_name(self, new_name: str):
        '''
        Set current task name.
        Usually used to overide copied task's name.
        '''
        pass

    @abstractmethod
    def set_description(self, new_description: str):
        '''
        Set current task description.
        Usually used to overide copied task's description.
        '''
        pass

    @abstractmethod
    def set_icon(self, new_icon: str):
        '''
        Set current task icon.
        Usually used to overide copied task's icon.
        '''
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
    def get_execution_id(self) -> str:
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
    def _get_full_cmd_name(self) -> str:
        pass

    @abstractmethod
    def _set_has_cli_interface(self):
        pass

    @abstractmethod
    def inject_env_files(self):
        pass

    @abstractmethod
    def _get_env_files(self) -> List[EnvFile]:
        pass

    @abstractmethod
    def inject_envs(self):
        pass

    @abstractmethod
    def _get_envs(self) -> List[Env]:
        pass

    @abstractmethod
    def inject_inputs(self):
        pass

    @abstractmethod
    def _get_inputs(self) -> List[AnyInput]:
        pass

    @abstractmethod
    def inject_checkers(self):
        pass

    @abstractmethod
    def _get_checkers(self) -> Iterable[TAnyTask]:
        pass

    @abstractmethod
    def inject_upstreams(self):
        pass

    @abstractmethod
    def _get_upstreams(self) -> Iterable[TAnyTask]:
        pass

    @abstractmethod
    def _get_combined_inputs(self) -> Iterable[AnyInput]:
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
    def render_any(
        self, val: Any, data: Optional[Mapping[str, Any]] = None
    ) -> Any:
        pass

    @abstractmethod
    def render_float(
        self,
        val: Union[JinjaTemplate, float],
        data: Optional[Mapping[str, Any]] = None
    ) -> float:
        pass

    @abstractmethod
    def render_int(
        self,
        val: Union[JinjaTemplate, int],
        data: Optional[Mapping[str, Any]] = None
    ) -> int:
        pass

    @abstractmethod
    def render_bool(
        self, 
        val: Union[JinjaTemplate, bool],
        data: Optional[Mapping[str, Any]] = None
    ) -> bool:
        pass

    @abstractmethod
    def render_str(
        self,
        val: JinjaTemplate,
        data: Optional[Mapping[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def render_file(
        self,
        location: JinjaTemplate,
        data: Optional[Mapping[str, Any]] = None
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
        '''
        Print result to stdout so that it can be processed further.
        e.g.: echo $(zrb explain solid) > solid-principle.txt

        You need to override this method
        if you want to show the result differently.
        '''
        pass
