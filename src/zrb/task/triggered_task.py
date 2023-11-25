from zrb.helper.typing import (
    Any, Callable, Iterable, List, Mapping, Optional, Union
)
from zrb.helper.typecheck import typechecked
from zrb.task.base_task import BaseTask
from zrb.task.any_task import AnyTask
from zrb.task.any_task_event_handler import (
    OnTriggered, OnWaiting, OnSkipped, OnStarted, OnReady, OnRetry, OnFailed
)
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

import asyncio
import datetime
import glob
import os
import croniter


@typechecked
class TriggeredTask(BaseTask):

    def __init__(
        self,
        name: str,
        task: AnyTask,
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
        checkers: Iterable[AnyTask] = [],
        interval: float = 1,
        schedule: Union[str, Iterable[str]] = [],
        watched_path: Union[str, Iterable[str]] = [],
        checking_interval: float = 0,
        retry: int = 2,
        retry_interval: float = 1,
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False
    ):
        inputs = list(inputs) + task._get_inputs()
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
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )
        self._task = task
        self._interval = interval
        self._set_schedule(schedule)
        self._set_watch_path(watched_path)

    def _set_watch_path(self, watched_path: Union[str, Iterable[str]]):
        if isinstance(watched_path, str) and watched_path != '':
            self._watched_paths: List[str] = [watched_path]
            return
        self._watched_paths: List[str] = watched_path

    def _set_schedule(self, schedule: Union[str, Iterable[str]]):
        if isinstance(schedule, str) and schedule != '':
            self._schedules: List[str] = [schedule]
            return
        self._schedules: List[str] = schedule

    async def run(self, *args: Any, **kwargs: Any):
        schedules = [self.render_str(schedule) for schedule in self._schedules]
        watched_path = [
            self.render_str(watched_path)
            for watched_path in self._watched_paths
        ]
        mod_times = self._get_mode_times(watched_path)
        scheduled_times: List[datetime.datetime] = []
        while True:
            should_run = False
            # check time
            start_time = datetime.datetime.now()
            for schedule in schedules:
                next_run = self._get_next_run(schedule, start_time)
                if next_run not in scheduled_times:
                    scheduled_times.append(next_run)
            for scheduled_time in list(scheduled_times):
                if scheduled_time not in scheduled_times:
                    continue
                if start_time > scheduled_time:
                    self.print_out_dark(f'Scheduled time: {scheduled_time}')
                    scheduled_times.remove(scheduled_time)
                    should_run = True
            # detect file changes
            current_mod_times = self._get_mode_times(watched_path)
            if not should_run:
                new_files = current_mod_times.keys() - mod_times.keys()
                for file in new_files:
                    self.print_out_dark(f'[+] New file detected: {file}')
                    should_run = True
                deleted_files = mod_times.keys() - current_mod_times.keys()
                for file in deleted_files:
                    self.print_out_dark(f'[-] File deleted: {file}')
                    should_run = True
                modified_files = {
                    file for file, mod_time in current_mod_times.items()
                    if file in mod_times and mod_times[file] != mod_time
                }
                for file in modified_files:
                    self.print_out_dark(f'[/] File modified: {file}')
                    should_run = True
                mod_times = current_mod_times
            # skip run
            if should_run:
                # Run
                fn = self._task.to_function(
                    is_async=True, raise_error=False, show_done_info=False
                )
                child_kwargs = {
                    key: kwargs[key]
                    for key in kwargs if key not in ['_task']
                }
                asyncio.create_task(fn(*args, **child_kwargs))
                self._play_bell()
            await asyncio.sleep(self._interval)

    def _get_mode_times(self, watched_path: List[str]) -> Mapping[str, float]:
        files_mod_times: Mapping[str, float] = {}
        for watch_path in watched_path:
            for file_name in glob.glob(watch_path):
                files_mod_times[file_name] = os.stat(file_name).st_mtime
        return files_mod_times

    def _get_next_run(
        self, cron_pattern: str, check_time: datetime.datetime
    ) -> datetime.datetime:
        margin = datetime.timedelta(seconds=self._interval/2.0)
        slightly_before_check_time = check_time - margin
        cron = croniter.croniter(cron_pattern, slightly_before_check_time)
        return cron.get_next(datetime.datetime)
