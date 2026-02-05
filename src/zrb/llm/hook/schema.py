from typing import Any, Dict, List, Optional, Union

from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator


class MatcherConfig:
    def __init__(
        self,
        field: str,
        operator: MatcherOperator,
        value: Any,
        case_sensitive: bool = True,
    ):
        self.field = field
        self.operator = operator
        self.value = value
        self.case_sensitive = case_sensitive


class CommandHookConfig:
    def __init__(
        self,
        command: str,
        shell: bool = True,
        working_dir: Optional[str] = None,
    ):
        self.command = command
        self.shell = shell
        self.working_dir = working_dir


class PromptHookConfig:
    def __init__(
        self,
        user_prompt_template: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ):
        self.user_prompt_template = user_prompt_template
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature


class AgentHookConfig:
    def __init__(
        self,
        system_prompt: str,
        tools: List[str] = None,
        model: Optional[str] = None,
    ):
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else []
        self.model = model


class HookConfig:
    def __init__(
        self,
        name: str,
        events: List[HookEvent],
        type: HookType,
        config: Union[CommandHookConfig, PromptHookConfig, AgentHookConfig],
        description: Optional[str] = None,
        matchers: List[MatcherConfig] = None,
        is_async: bool = False,
        enabled: bool = True,
        timeout: Optional[int] = None,
        env: Dict[str, str] = None,
        priority: int = 0,
    ):
        self.name = name
        self.events = events
        self.type = type
        self.config = config
        self.description = description
        self.matchers = matchers if matchers is not None else []
        self.is_async = is_async
        self.enabled = enabled
        self.timeout = timeout
        self.env = env if env is not None else {}
        self.priority = priority
