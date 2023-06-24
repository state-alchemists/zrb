from typing import Any, Callable, Iterable, List, Optional, TypeVar, Union
from typeguard import typechecked
from .base_task import BaseTask, Group
from .task import Task
from .cmd_task import CmdTask
from ..task_env.env import Env
from ..task_env.env_file import EnvFile
from ..task_input.base_input import BaseInput

TFlowNode = TypeVar('TFlowNode', bound='FlowNode')


@typechecked
class FlowNode():
    def __init__(
        self,
        name: str,
        inputs: Iterable[BaseInput] = [],
        envs: Iterable[Env] = [],
        env_files: Iterable[EnvFile] = [],
        upstreams: Iterable[BaseTask] = [],
        icon: Optional[str] = None,
        color: Optional[str] = None,
        cmd: Union[str, Iterable[str]] = '',
        cmd_path: str = '',
        preexec_fn: Optional[Callable[[], Any]] = None,
        run: Optional[Callable[..., Any]] = None,
        nodes: List[Union[TFlowNode, List[TFlowNode]]] = []
    ):
        self._name = name
        self._inputs = inputs
        self._envs = envs
        self._env_files = env_files
        self._upstreams = upstreams
        self._icon = icon
        self._color = color
        self._cmd = cmd
        self._cmd_path = cmd_path
        self._preexec_fn = preexec_fn
        self._run_function = run
        self._nodes = nodes

    def to_task(
        self,
        upstreams: List[BaseTask] = [],
        inputs: List[BaseInput] = [],
        envs: List[Env] = [],
        env_files: List[EnvFile] = [],
    ):
        if self._run_function is not None:
            return Task(
                name=self._name,
                upstreams=upstreams + self._upstreams,
                inputs=inputs + self._inputs,
                envs=envs + self._envs,
                env_files=env_files + self._env_files,
                icon=self._icon,
                color=self._color,
                run=self._run_function
            )
        if self._cmd != '' or self._cmd_path != '':
            return CmdTask(
                name=self._name,
                upstreams=upstreams + self._upstreams,
                inputs=inputs + self._inputs,
                envs=envs + self._envs,
                env_files=env_files + self._env_files,
                icon=self._icon,
                color=self._color,
                cmd=self._cmd,
                cmd_path=self._cmd_path,
                preexec_fn=self._preexec_fn
            )
        return FlowTask(
            name=self._name,
            upstreams=upstreams + self._upstreams,
            inputs=inputs + self._inputs,
            envs=envs + self._envs,
            env_files=env_files + self._env_files,
            icon=self._icon,
            color=self._color,
            nodes=self._nodes
        )


@typechecked
class FlowTask(BaseTask):

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
        upstreams: Iterable[BaseTask] = [],
        checkers: Iterable[BaseTask] = [],
        checking_interval: float = 0,
        retry: int = 2,
        retry_interval: float = 1,
        nodes: List[Union[FlowNode, List[FlowNode]]] = [],
        skip_execution: Union[bool, str, Callable[..., bool]] = False
    ):
        final_upstreams: List[Task] = upstreams
        for node in nodes:
            flow_nodes = self._get_flow_nodes(node)
            new_upstreams: List[Task] = [
                flow_node.to_task(
                    upstreams=final_upstreams,
                    inputs=inputs,
                    envs=envs,
                    env_files=env_files
                )
                for flow_node in flow_nodes
            ]
            final_upstreams = new_upstreams
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
            upstreams=final_upstreams,
            checkers=checkers,
            checking_interval=checking_interval,
            retry=retry,
            retry_interval=retry_interval,
            skip_execution=skip_execution,
            run=lambda *args, **kwargs: kwargs.get('_task').print_out('👌')
        )

    def _get_flow_nodes(
        self, node: Union[FlowNode, List[FlowNode]]
    ) -> List[FlowNode]:
        if isinstance(node, FlowNode):
            return [node]
        return node
