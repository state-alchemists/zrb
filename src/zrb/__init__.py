from zrb.helper.default_env import inject_default_env
from zrb.runner import runner
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
from zrb.task.base_remote_cmd_task import BaseRemoteCmdTask, RemoteConfig
from zrb.task.checker import Checker
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task.docker_compose_task import DockerComposeTask, ServiceConfig
from zrb.task.flow_task import FlowTask
from zrb.task.http_checker import HTTPChecker
from zrb.task.notifier import Notifier
from zrb.task.parallel import AnyParallel, Parallel
from zrb.task.path_checker import PathChecker
from zrb.task.path_watcher import PathWatcher
from zrb.task.port_checker import PortChecker
from zrb.task.recurring_task import RecurringTask
from zrb.task.remote_cmd_task import RemoteCmdTask
from zrb.task.resource_maker import Replacement, ReplacementMutator, ResourceMaker
from zrb.task.rsync_task import RsyncTask
from zrb.task.task import Task
from zrb.task.time_watcher import TimeWatcher
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_group.group import Group
from zrb.task_input.any_input import AnyInput
from zrb.task_input.bool_input import BoolInput
from zrb.task_input.choice_input import ChoiceInput
from zrb.task_input.float_input import FloatInput
from zrb.task_input.int_input import IntInput
from zrb.task_input.password_input import PasswordInput
from zrb.task_input.str_input import StrInput
from zrb.task_input.task_input import Input

assert runner
assert AnyTask
assert OnTriggered
assert OnWaiting
assert OnSkipped
assert OnStarted
assert OnReady
assert OnRetry
assert OnFailed
assert AnyParallel
assert Parallel
assert python_task
assert Task
assert CmdTask
assert DockerComposeTask
assert ServiceConfig
assert BaseRemoteCmdTask
assert RemoteConfig
assert RemoteCmdTask
assert RsyncTask
assert Notifier
assert Checker
assert HTTPChecker
assert PortChecker
assert PathChecker
assert PathWatcher
assert TimeWatcher
assert ResourceMaker
assert FlowTask
assert RecurringTask
assert Replacement
assert ReplacementMutator
assert AnyInput
assert Input
assert BoolInput
assert ChoiceInput
assert FloatInput
assert IntInput
assert PasswordInput
assert StrInput
assert Env
assert EnvFile
assert Group

inject_default_env()
