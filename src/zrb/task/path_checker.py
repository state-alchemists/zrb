from zrb.helper.typing import Any, Callable, Iterable, Optional, Union, TypeVar
from zrb.helper.typecheck import typechecked
from zrb.task.checker import Checker
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnTriggered, OnWaiting, OnSkipped, OnStarted, OnReady, OnRetry, OnFailed
)
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import glob

TPathChecker = TypeVar('TPathChecker', bound='PathChecker')


@typechecked
class PathChecker(Checker):

    def __init__(
        self,
        name: str = 'check-path',
        group: Optional[Group] = None,
        inputs: Iterable[AnyInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: str = '',
        upstreams: Iterable[AnyTask] = [],
        on_triggered: Optional[OnTriggered] = None,
        on_waiting: Optional[OnWaiting] = None,
        on_skipped: Optional[OnSkipped] = None,
        on_started: Optional[OnStarted] = None,
        on_ready: Optional[OnReady] = None,
        on_retry: Optional[OnRetry] = None,
        on_failed: Optional[OnFailed] = None,
        path: str = '',
        checking_interval: Union[int, float] = 0.1,
        progress_interval: Union[int, float] = 5,
        expected_result: bool = True,
        should_execute: Union[bool, str, Callable[..., bool]] = True
    ):
        Checker.__init__(
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
            on_triggered=on_triggered,
            on_waiting=on_waiting,
            on_skipped=on_skipped,
            on_started=on_started,
            on_ready=on_ready,
            on_retry=on_retry,
            on_failed=on_failed,
            checking_interval=checking_interval,
            progress_interval=progress_interval,
            expected_result=expected_result,
            should_execute=should_execute,
        )
        self._path = path
        self._rendered_path: str = ''

    def copy(self) -> TPathChecker:
        return super().copy()

    def to_function(
        self,
        env_prefix: str = '',
        raise_error: bool = True,
        is_async: bool = False,
        show_done_info: bool = True
    ) -> Callable[..., bool]:
        return super().to_function(
            env_prefix, raise_error, is_async, show_done_info
        )

    async def run(self, *args: Any, **kwargs: Any) -> bool:
        self._rendered_path = self.render_str(self._path)
        return await super().run(*args, **kwargs)

    async def inspect(self, *args: Any, **kwargs: Any) -> bool:
        label = f'Checking {self._rendered_path}'
        try:
            if len(glob.glob(self._rendered_path, recursive=True)) > 0:
                self.print_out(f'{label} (Exist)')
                return True
            self.show_progress(f'{label} (Not Exist)')
        except Exception:
            self.show_progress(f'{label} Cannot inspect')
        return False
