"""Public API surface for the Zrb framework.

Every name in `__all__` resolves on first access (PEP 562), so `import zrb`
stays cheap: a caller who wants `Task` and `make_task` does not pay for the
agent stack, the CLI, or the built-in task tree. `from zrb import X`, `zrb.X`,
`dir(zrb)` and `from zrb import *` all work.

Importing this package does not import `zrb.builtin`, which registers the
built-in tasks on `cli`. `zrb.__main__` imports it before loading any init
source, so the CLI sees the full tree; a library that wants the built-ins does
`from zrb import builtin`.
"""

import importlib
from typing import TYPE_CHECKING

# The names below are resolved at runtime by `__getattr__`; these imports are
# for readers, IDEs and pyright only.
if TYPE_CHECKING:
    from zrb import builtin
    from zrb.attr.tpl import Tpl
    from zrb.attr.type import (
        BoolAttr,
        FloatAttr,
        IntAttr,
        StrAttr,
        StrDictAttr,
        StrListAttr,
    )
    from zrb.callback.any_callback import AnyCallback
    from zrb.callback.callback import Callback
    from zrb.cmd.cmd_result import CmdResult
    from zrb.cmd.cmd_val import Cmd, CmdPath
    from zrb.config.config import CFG, Config
    from zrb.config.theme import register_theme
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
    from zrb.llm.contracts.config.limiter import LLMLimiter, llm_limiter
    from zrb.llm.contracts.config.model_resolver import ModelResolver, model_resolver
    from zrb.llm.capabilities.hook import HookContext, HookEvent, HookResult
    from zrb.llm.capabilities.hook.manager import HookManager, hook_manager
    from zrb.llm.capabilities.hook.registry import HookRegistry, hook_registry
    from zrb.llm.capabilities.permission import ALLOW, ASK, DENY, PermissionPolicy, Rule
    from zrb.llm.capabilities.prompt.manager import PromptManager
    from zrb.llm.capabilities.prompt.registry import PromptRegistry, prompt_registry
    from zrb.llm.contracts.shared.tool_registry import ToolRegistry, tool_registry
    from zrb.llm.capabilities.skill import Skill, SkillRegistry
    from zrb.llm.capabilities.skill.manager import SkillManager, skill_manager
    from zrb.llm.capabilities.skill.registry import skill_registry
    from zrb.llm.orchestration.subagent.manager.manager import (
        SubAgentDefinition,
        SubAgentManager,
        sub_agent_manager,
    )
    from zrb.llm.orchestration.subagent.registry import SubAgentRegistry, sub_agent_registry
    from zrb.llm.orchestration.task.chat.task import LLMChatTask
    from zrb.llm.orchestration.task.llm_task import LLMTask
    from zrb.llm.capabilities.tool_call.always_approve import (
        register_always_auto_approve,
        register_default_auto_approve,
        register_default_auto_approve_if,
    )
    from zrb.llm.presentation.ui.any_ui import AnyUI
    from zrb.llm.presentation.ui.trigger import TriggerMessage, TriggerReply
    from zrb.llm.contracts.util.capabilities import model_capabilities
    from zrb.llm.presentation.voice.manager import (
        STTServiceManager,
        TTSServiceManager,
        stt_manager,
        tts_manager,
    )
    from zrb.llm.presentation.voice.registry import (
        STTServiceRegistry,
        TTSServiceRegistry,
        stt_registry,
        tts_registry,
    )
    from zrb.llm.presentation.voice.spec import STTServiceSpec, TTSServiceSpec
    from zrb.remote.inventory import Host, Target, host_inventory, target_inventory
    from zrb.runner.cli import Cli, cli
    from zrb.runner.web_schema.user import User
    from zrb.session.session import Session
    from zrb.task.any_task import AnyTask
    from zrb.task.base.base_task import BaseTask
    from zrb.task.base_trigger import BaseTrigger
    from zrb.task.cmd_task import CmdTask
    from zrb.task.http_check import HttpCheck
    from zrb.task.make_task import make_task
    from zrb.task.rsync_task import RsyncTask
    from zrb.task.scaffolder import Scaffolder
    from zrb.task.scheduler import Scheduler
    from zrb.task.task import Task
    from zrb.task.tcp_check import TcpCheck
    from zrb.util.load import load_file, load_module
    from zrb.util.stream import to_infinite_stream
    from zrb.xcom.xcom import Xcom

__all__ = [
    "builtin",
    "BoolAttr",
    "FloatAttr",
    "IntAttr",
    "StrAttr",
    "StrDictAttr",
    "StrListAttr",
    "Tpl",
    "AnyCallback",
    "Callback",
    "CmdResult",
    "Cmd",
    "CmdPath",
    "CFG",
    "Config",
    "web_auth_config",
    "AnyContentTransformer",
    "ContentTransformer",
    "AnyContext",
    "AnySharedContext",
    "Context",
    "SharedContext",
    "AnyEnv",
    "Env",
    "EnvFile",
    "EnvMap",
    "AnyGroup",
    "Group",
    "AnyInput",
    "BaseInput",
    "BoolInput",
    "FloatInput",
    "IntInput",
    "OptionInput",
    "PasswordInput",
    "StrInput",
    "TextInput",
    "Cli",
    "cli",
    "User",
    "Session",
    "AnyTask",
    "BaseTask",
    "BaseTrigger",
    "CmdTask",
    "Host",
    "Target",
    "host_inventory",
    "target_inventory",
    "HttpCheck",
    "make_task",
    "RsyncTask",
    "Scaffolder",
    "Scheduler",
    "Task",
    "TcpCheck",
    "load_file",
    "load_module",
    "to_infinite_stream",
    "Xcom",
    "LLMTask",
    "LLMChatTask",
    "LLMLimiter",
    "llm_limiter",
    "ModelResolver",
    "model_resolver",
    "SubAgentManager",
    "sub_agent_manager",
    "SubAgentDefinition",
    "SubAgentRegistry",
    "sub_agent_registry",
    "HookManager",
    "hook_manager",
    "HookEvent",
    "HookContext",
    "HookResult",
    "HookRegistry",
    "hook_registry",
    "SkillManager",
    "skill_manager",
    "Skill",
    "SkillRegistry",
    "skill_registry",
    "PromptManager",
    "PromptRegistry",
    "prompt_registry",
    "STTServiceManager",
    "STTServiceRegistry",
    "STTServiceSpec",
    "stt_manager",
    "stt_registry",
    "TTSServiceManager",
    "TTSServiceRegistry",
    "TTSServiceSpec",
    "tts_manager",
    "tts_registry",
    "ToolRegistry",
    "tool_registry",
    "AnyUI",
    "TriggerMessage",
    "TriggerReply",
    "model_capabilities",
    "register_theme",
    "register_always_auto_approve",
    "register_default_auto_approve",
    "register_default_auto_approve_if",
    "PermissionPolicy",
    "Rule",
    "ALLOW",
    "DENY",
    "ASK",
]

# name -> module that defines it, resolved on first access.
_LAZY_EXPORTS = {
    "builtin": "zrb.builtin",
    "BoolAttr": "zrb.attr.type",
    "FloatAttr": "zrb.attr.type",
    "IntAttr": "zrb.attr.type",
    "StrAttr": "zrb.attr.type",
    "StrDictAttr": "zrb.attr.type",
    "StrListAttr": "zrb.attr.type",
    "Tpl": "zrb.attr.tpl",
    "AnyCallback": "zrb.callback.any_callback",
    "Callback": "zrb.callback.callback",
    "CmdResult": "zrb.cmd.cmd_result",
    "Cmd": "zrb.cmd.cmd_val",
    "CmdPath": "zrb.cmd.cmd_val",
    "CFG": "zrb.config.config",
    "Config": "zrb.config.config",
    "web_auth_config": "zrb.config.web_auth_config",
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
    "Cli": "zrb.runner.cli",
    "cli": "zrb.runner.cli",
    "User": "zrb.runner.web_schema.user",
    "Session": "zrb.session.session",
    "AnyTask": "zrb.task.any_task",
    "BaseTask": "zrb.task.base.base_task",
    "BaseTrigger": "zrb.task.base_trigger",
    "CmdTask": "zrb.task.cmd_task",
    "Host": "zrb.remote.inventory",
    "Target": "zrb.remote.inventory",
    "host_inventory": "zrb.remote.inventory",
    "target_inventory": "zrb.remote.inventory",
    "HttpCheck": "zrb.task.http_check",
    "make_task": "zrb.task.make_task",
    "RsyncTask": "zrb.task.rsync_task",
    "Scaffolder": "zrb.task.scaffolder",
    "Scheduler": "zrb.task.scheduler",
    "Task": "zrb.task.task",
    "TcpCheck": "zrb.task.tcp_check",
    "load_file": "zrb.util.load",
    "load_module": "zrb.util.load",
    "to_infinite_stream": "zrb.util.stream",
    "Xcom": "zrb.xcom.xcom",
    "LLMTask": "zrb.llm.orchestration.task.llm_task",
    "LLMChatTask": "zrb.llm.orchestration.task.chat.task",
    "LLMLimiter": "zrb.llm.contracts.config.limiter",
    "llm_limiter": "zrb.llm.contracts.config.limiter",
    "ModelResolver": "zrb.llm.contracts.config.model_resolver",
    "model_resolver": "zrb.llm.contracts.config.model_resolver",
    "SubAgentManager": "zrb.llm.orchestration.subagent.manager.manager",
    "sub_agent_manager": "zrb.llm.orchestration.subagent.manager.manager",
    "SubAgentDefinition": "zrb.llm.orchestration.subagent.manager.manager",
    "SubAgentRegistry": "zrb.llm.orchestration.subagent.registry",
    "sub_agent_registry": "zrb.llm.orchestration.subagent.registry",
    "HookManager": "zrb.llm.capabilities.hook.manager",
    "hook_manager": "zrb.llm.capabilities.hook.manager",
    "HookEvent": "zrb.llm.capabilities.hook",
    "HookContext": "zrb.llm.capabilities.hook",
    "HookResult": "zrb.llm.capabilities.hook",
    "HookRegistry": "zrb.llm.capabilities.hook.registry",
    "hook_registry": "zrb.llm.capabilities.hook.registry",
    "SkillManager": "zrb.llm.capabilities.skill.manager",
    "skill_manager": "zrb.llm.capabilities.skill.manager",
    "Skill": "zrb.llm.capabilities.skill",
    "SkillRegistry": "zrb.llm.capabilities.skill",
    "skill_registry": "zrb.llm.capabilities.skill.registry",
    "PromptManager": "zrb.llm.capabilities.prompt.manager",
    "PromptRegistry": "zrb.llm.capabilities.prompt.registry",
    "prompt_registry": "zrb.llm.capabilities.prompt.registry",
    "STTServiceManager": "zrb.llm.presentation.voice.manager",
    "STTServiceRegistry": "zrb.llm.presentation.voice.registry",
    "STTServiceSpec": "zrb.llm.presentation.voice.spec",
    "stt_manager": "zrb.llm.presentation.voice.manager",
    "stt_registry": "zrb.llm.presentation.voice.registry",
    "TTSServiceManager": "zrb.llm.presentation.voice.manager",
    "TTSServiceRegistry": "zrb.llm.presentation.voice.registry",
    "TTSServiceSpec": "zrb.llm.presentation.voice.spec",
    "tts_manager": "zrb.llm.presentation.voice.manager",
    "tts_registry": "zrb.llm.presentation.voice.registry",
    "ToolRegistry": "zrb.llm.contracts.shared.tool_registry",
    "tool_registry": "zrb.llm.contracts.shared.tool_registry",
    "AnyUI": "zrb.llm.presentation.ui.any_ui",
    "TriggerMessage": "zrb.llm.presentation.ui.trigger",
    "TriggerReply": "zrb.llm.presentation.ui.trigger",
    "model_capabilities": "zrb.llm.contracts.util.capabilities",
    "register_theme": "zrb.config.theme",
    "register_always_auto_approve": "zrb.llm.capabilities.tool_call.always_approve",
    "register_default_auto_approve": "zrb.llm.capabilities.tool_call.always_approve",
    "register_default_auto_approve_if": "zrb.llm.capabilities.tool_call.always_approve",
    "PermissionPolicy": "zrb.llm.capabilities.permission",
    "Rule": "zrb.llm.capabilities.permission",
    "ALLOW": "zrb.llm.capabilities.permission",
    "DENY": "zrb.llm.capabilities.permission",
    "ASK": "zrb.llm.capabilities.permission",
}

_NO_LLM_CONFIG = (
    "was removed in 3.0.0: every LLM setting is a `CFG` knob (`CFG.LLM_MODEL`, "
    "`CFG.LLM_API_KEY`, ...) and models resolve through `model_resolver`."
)

# Names `from zrb import ...` used to offer, and what to use instead, so code
# written for an older zrb (or a plugin not yet updated) fails with directions.
_RETIRED_EXPORTS = {
    "LLMConfig": _NO_LLM_CONFIG,
    "llm_config": _NO_LLM_CONFIG,
    "UICommands": (
        "was removed in 3.0.0: command aliases are `UIConfig` fields, or the "
        "{ENV_PREFIX}_LLM_UI_COMMAND_* settings."
    ),
    "fstring": "was removed in 3.0.0: it was an alias of `str`; use `str`.",
}


def __getattr__(name: str):
    """Resolve a public export on first access (PEP 562).

    The result is cached in the module namespace, so the second access is a
    plain attribute read and `vars(zrb)` matches what `dir(zrb)` promises.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is not None:
        module = importlib.import_module(module_name)
        # `builtin` names a package; every other export names a member of one.
        if module_name == f"{__name__}.{name}":
            value = module
        else:
            value = getattr(module, name)
        globals()[name] = value
        return value
    if name in _RETIRED_EXPORTS:
        # An ImportError, not an AttributeError: `from zrb import X` turns an
        # AttributeError into a bare "cannot import name", dropping the hint.
        # lazy: transitively heavy — config pulls importlib.metadata; only the
        # hint below needs it, on a path that raises anyway.
        from zrb.config.config import CFG

        hint = _RETIRED_EXPORTS[name].replace("{ENV_PREFIX}", CFG.ENV_PREFIX)
        raise ImportError(
            f"zrb.{name} {hint} See docs/advanced-topics/upgrading-guide.md.",
            name=name,
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Keep lazily-exported names visible to `dir()` (PEP 562)."""
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
