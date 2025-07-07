import importlib
from typing import TYPE_CHECKING, Any

_LAZY_LOAD = {
    "AnyAttr": "zrb.attr.type",
    "BoolAttr": "zrb.attr.type",
    "FloatAttr": "zrb.attr.type",
    "IntAttr": "zrb.attr.type",
    "StrAttr": "zrb.attr.type",
    "StrDictAttr": "zrb.attr.type",
    "fstring": "zrb.attr.type",
    "AnyCallback": "zrb.callback.any_callback",
    "Callback": "zrb.callback.callback",
    "CmdResult": "zrb.cmd.cmd_result",
    "Cmd": "zrb.cmd.cmd_val",
    "CmdPath": "zrb.cmd.cmd_val",
    "CFG": "zrb.config.config",
    "AnyContentTransformer": "zrb.content_transformer.any_content_transformer",
    "ContentTransformer": "zrb.content_transformer.content_transformer",
    "AnyContext": "zrb.context.any_context",
    "AnySharedContext": "zrb.context.any_shared_context",
    "Context": "zrb.context.context",
    "SharedContext": "zrb.context.shared_context",
    "AnyEnv": "zrb.env.any_env",
    "Env": "zrb.env.env",
    "EnvFile": "zrb.env.env_file",
    "EnvMap": "zrb.env.env_map",
    "AnyGroup": "zrb.group.any_group",
    "Group": "zrb.group.group",
    "AnyInput": "zrb.input.any_input",
    "BaseInput": "zrb.input.base_input",
    "BoolInput": "zrb.input.bool_input",
    "FloatInput": "zrb.input.float_input",
    "IntInput": "zrb.input.int_input",
    "OptionInput": "zrb.input.option_input",
    "PasswordInput": "zrb.input.password_input",
    "StrInput": "zrb.input.str_input",
    "TextInput": "zrb.input.text_input",
    "llm_config": "zrb.config.llm_config",
    "llm_rate_limitter": "zrb.config.llm_rate_limitter",
    "cli": "zrb.runner.cli",
    "web_auth_config": "zrb.config.web_auth_config",
    "User": "zrb.runner.web_schema.user",
    "Session": "zrb.session.session",
    "AnyTask": "zrb.task.any_task",
    "BaseTask": "zrb.task.base_task",
    "BaseTrigger": "zrb.task.base_trigger",
    "CmdTask": "zrb.task.cmd_task",
    "HttpCheck": "zrb.task.http_check",
    "ConversationHistoryData": "zrb.task.llm.history",
    "LLMTask": "zrb.task.llm_task",
    "make_task": "zrb.task.make_task",
    "RsyncTask": "zrb.task.rsync_task",
    "Scaffolder": "zrb.task.scaffolder",
    "Scheduler": "zrb.task.scheduler",
    "Task": "zrb.task.task",
    "TcpCheck": "zrb.task.tcp_check",
    "load_file": "zrb.util.load",
    "load_module": "zrb.util.load",
    "Xcom": "zrb.xcom.xcom",
}

if TYPE_CHECKING:
    from zrb.attr.type import (
        AnyAttr,
        BoolAttr,
        FloatAttr,
        IntAttr,
        StrAttr,
        StrDictAttr,
        fstring,
    )
    from zrb.callback.any_callback import AnyCallback
    from zrb.callback.callback import Callback
    from zrb.cmd.cmd_result import CmdResult
    from zrb.cmd.cmd_val import Cmd, CmdPath
    from zrb.config.config import CFG
    from zrb.config.llm_config import llm_config
    from zrb.config.llm_rate_limitter import llm_rate_limitter
    from zrb.config.web_auth_config import web_auth_config
    from zrb.content_transformer.any_content_transformer import AnyContentTransformer
    from zrb.content_transformer.content_transformer import ContentTransformer
    from zrb.context.any_context import AnyContext
    from zrb.context.any_shared_context import AnySharedContext
    from zrb.context.context import Context
    from zrb.context.shared_context import SharedContext
    from zrb.env.any_env import AnyEnv
    from zrb.env.env import Env
    from zrb.env.env_file import EnvFile
    from zrb.env.env_map import EnvMap
    from zrb.group.any_group import AnyGroup
    from zrb.group.group import Group
    from zrb.input.any_input import AnyInput
    from zrb.input.base_input import BaseInput
    from zrb.input.bool_input import BoolInput
    from zrb.input.float_input import FloatInput
    from zrb.input.int_input import IntInput
    from zrb.input.option_input import OptionInput
    from zrb.input.password_input import PasswordInput
    from zrb.input.str_input import StrInput
    from zrb.input.text_input import TextInput
    from zrb.runner.cli import cli
    from zrb.runner.web_schema.user import User
    from zrb.session.session import Session
    from zrb.task.any_task import AnyTask
    from zrb.task.base_task import BaseTask
    from zrb.task.base_trigger import BaseTrigger
    from zrb.task.cmd_task import CmdTask
    from zrb.task.http_check import HttpCheck
    from zrb.task.llm.history import ConversationHistoryData
    from zrb.task.llm_task import LLMTask
    from zrb.task.make_task import make_task
    from zrb.task.rsync_task import RsyncTask
    from zrb.task.scaffolder import Scaffolder
    from zrb.task.scheduler import Scheduler
    from zrb.task.task import Task
    from zrb.task.tcp_check import TcpCheck
    from zrb.util.load import load_file, load_module
    from zrb.xcom.xcom import Xcom


def __getattr__(name: str) -> Any:
    if name in _LAZY_LOAD:
        module = importlib.import_module(_LAZY_LOAD[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Eager load CFG
CFG = __getattr__("CFG")
if CFG.LOAD_BUILTIN:
    from zrb import builtin

    assert builtin
