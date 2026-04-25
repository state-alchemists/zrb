"""Public API surface for the Zrb framework.

Imports below are grouped by concern (Config, Context, Tasks, LLM, ...) so a
new contributor can scan this file and understand what `from zrb import X`
exposes. Module-level singletons are typed so IDEs reveal what each one is.
"""

# --- Builtin tasks (registered as side-effect of import) ------------------
from zrb import builtin

# --- Attribute descriptors (deferred-eval property types) -----------------
from zrb.attr.type import (
    AnyAttr,
    BoolAttr,
    FloatAttr,
    IntAttr,
    StrAttr,
    StrDictAttr,
    fstring,
)

# --- Callbacks ------------------------------------------------------------
from zrb.callback.any_callback import AnyCallback
from zrb.callback.callback import Callback

# --- Command results / values --------------------------------------------
from zrb.cmd.cmd_result import CmdResult
from zrb.cmd.cmd_val import Cmd, CmdPath

# --- Config singleton -----------------------------------------------------
from zrb.config.config import CFG, Config
from zrb.config.web_auth_config import web_auth_config

# --- Content transformers -------------------------------------------------
from zrb.content_transformer.any_content_transformer import AnyContentTransformer
from zrb.content_transformer.content_transformer import ContentTransformer

# --- Context (per-task and shared) ---------------------------------------
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext

# --- Environment variables -----------------------------------------------
from zrb.env.any_env import AnyEnv
from zrb.env.env import Env
from zrb.env.env_file import EnvFile
from zrb.env.env_map import EnvMap

# --- Group (CLI command grouping) ----------------------------------------
from zrb.group.any_group import AnyGroup
from zrb.group.group import Group

# --- Inputs ---------------------------------------------------------------
from zrb.input.any_input import AnyInput
from zrb.input.base_input import BaseInput
from zrb.input.bool_input import BoolInput
from zrb.input.float_input import FloatInput
from zrb.input.int_input import IntInput
from zrb.input.option_input import OptionInput
from zrb.input.password_input import PasswordInput
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput

# --- LLM agent / chat / config / managers --------------------------------
from zrb.llm.agent.manager import SubAgentManager, sub_agent_manager
from zrb.llm.config.config import LLMConfig, llm_config
from zrb.llm.config.limiter import LLMLimiter, llm_limiter
from zrb.llm.hook.manager import HookManager, hook_manager
from zrb.llm.prompt.tool_guidance import ToolGuidance
from zrb.llm.skill.manager import SkillManager, skill_manager
from zrb.llm.task.llm_chat_task import LLMChatTask
from zrb.llm.task.llm_task import LLMTask

# --- Runner (CLI + web schemas) ------------------------------------------
from zrb.runner.cli import Cli, cli
from zrb.runner.web_schema.user import User

# --- Session --------------------------------------------------------------
from zrb.session.session import Session

# --- Tasks ---------------------------------------------------------------
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask
from zrb.task.base_trigger import BaseTrigger
from zrb.task.cmd_task import CmdTask
from zrb.task.http_check import HttpCheck
from zrb.task.make_task import make_task
from zrb.task.rsync_task import RsyncTask
from zrb.task.scaffolder import Scaffolder
from zrb.task.scheduler import Scheduler
from zrb.task.task import Task
from zrb.task.tcp_check import TcpCheck

# --- Util & XCom ---------------------------------------------------------
from zrb.util.load import load_file, load_module
from zrb.util.stream import to_infinite_stream
from zrb.xcom.xcom import Xcom

# --- Typed annotations for module-level singletons -----------------------
# `CFG`, `cli`, `*_manager`, `llm_config`, etc. are exported as instances.
# Type-annotating them at this scope helps IDEs and static analysers report
# the right interface when users do `from zrb import hook_manager`.
CFG: Config = CFG
cli: Cli = cli
llm_config: LLMConfig = llm_config
llm_limiter: LLMLimiter = llm_limiter
sub_agent_manager: SubAgentManager = sub_agent_manager
hook_manager: HookManager = hook_manager
skill_manager: SkillManager = skill_manager

__all__ = [
    "builtin",
    "AnyAttr",
    "BoolAttr",
    "FloatAttr",
    "IntAttr",
    "StrAttr",
    "StrDictAttr",
    "fstring",
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
    "ToolGuidance",
    "LLMConfig",
    "llm_config",
    "LLMLimiter",
    "llm_limiter",
    "SubAgentManager",
    "sub_agent_manager",
    "HookManager",
    "hook_manager",
    "SkillManager",
    "skill_manager",
]
