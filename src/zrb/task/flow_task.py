from collections.abc import Callable, Iterable
from typing import Optional, TypeVar, Union

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
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
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput

logger.debug(colored("Loading zrb.task.flow_task", attrs=["dark"]))

TFlowTask = TypeVar("TFlowTask", bound="FlowTask")


@typechecked
class FlowTask(BaseTask):
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
        steps: list[Union[AnyTask, list[AnyTask]]] = [],
        should_execute: Union[bool, str, Callable[..., bool]] = True,
        return_upstream_result: bool = False,
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
            upstreams=self._create_flow_upstreams(
                steps=steps,
                upstreams=list(upstreams),
                inputs=list(inputs),
                envs=list(envs),
                env_files=list(env_files),
            ),
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
            should_execute=should_execute,
            return_upstream_result=return_upstream_result,
        )

    def copy(self) -> TFlowTask:
        return super().copy()

    def _create_flow_upstreams(
        self,
        steps: list[Union[AnyTask, list[AnyTask]]],
        upstreams: list[AnyTask],
        inputs: list[AnyInput],
        envs: list[Env],
        env_files: list[EnvFile],
    ) -> list[AnyTask]:
        flow_upstreams = upstreams
        for step in steps:
            tasks = [task.copy() for task in self._step_to_tasks(step)]
            new_upstreams = self._create_embeded_tasks(
                tasks=tasks,
                upstreams=flow_upstreams,
                inputs=inputs,
                envs=envs,
                env_files=env_files,
            )
            flow_upstreams = new_upstreams
        return flow_upstreams

    def _step_to_tasks(self, step: Union[AnyTask, list[AnyTask]]) -> list[AnyTask]:
        if isinstance(step, AnyTask):
            return [step]
        return step

    def _create_embeded_tasks(
        self,
        tasks: list[AnyTask],
        upstreams: list[AnyTask],
        inputs: list[AnyInput],
        envs: list[Env],
        env_files: list[EnvFile],
    ) -> list[AnyTask]:
        embeded_tasks: list[AnyTask] = []
        for embeded_task in tasks:
            embeded_task_upstreams = self._get_all_upstreams(tasks=[embeded_task])
            for embeded_task_upstream in embeded_task_upstreams:
                embeded_task_upstream.add_upstream(*upstreams)
            embeded_task.add_env(*envs)
            embeded_task.add_env_file(*env_files)
            embeded_task.add_input(*inputs)
            embeded_tasks.append(embeded_task)
        return embeded_tasks

    def _get_all_upstreams(self, tasks: list[AnyTask]):
        all_upstreams = []
        for task in tasks:
            upstreams = task._get_upstreams()
            if len(upstreams) == 0:
                all_upstreams.append(task)
                continue
            for upstream in upstreams:
                if len(upstream._get_upstreams()) == 0:
                    all_upstreams.append(upstream)
                    continue
                all_upstreams += self._get_all_upstreams([upstream])
        return all_upstreams
