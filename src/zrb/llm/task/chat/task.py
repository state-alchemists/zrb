"""`LLMChatTask` — the conversational task type that powers `zrb llm chat`.

Wires together: tools/skills/hooks resolution, UI factory selection (default
TUI, std-out, http, multi-UI), approval-channel orchestration, history
manager + snapshot lifecycle, and the inner `LLMTask` execution. Heavy.

`__init__` and the post-construction configuration API (the `set_*`/`append_*`/
`prepend_*` mutators and their matching read accessors) stay here — that state
is this task's own construction-time data, not a separate object's. The two
files below hold genuinely separate behavior:

  execution.py - build the inner LLMTask per turn, run `exec_action`, teardown
  running.py   - resolve UIs/triggers/custom commands, run the loop

For the public API and authoring patterns, see:
  docs/task-types/llmchat-task.md
For the end-to-end request lifecycle (CLI -> LLMChatTask -> agent run -> UI),
see docs/advanced-topics/llm-chat-lifecycle.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, AsyncIterable, Callable

from zrb.attr.type import BoolAttr, StrAttr, StrListAttr, fstring
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.llm.agent import AnyToolConfirmation
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.hook.manager import HookManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.task.chat.execution import ChatExecution
from zrb.llm.task.chat.running import ChatRunning
from zrb.llm.task.history_config import HistoryConfig
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
    replace_in_file_formatter,
    write_file_formatter,
)
from zrb.task.any_task import AnyTask
from zrb.task.base.base_task import BaseTask

if TYPE_CHECKING:
    from rich.theme import Theme

    from zrb.llm.agent.common import HistoryProcessor
    from zrb.llm.agent.types import (
        AbstractCapability,
        AbstractToolset,
        Model,
        ModelSettings,
        Tool,
        ToolFuncEither,
        UserContent,
    )
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.permission import PermissionPolicyInput
    from zrb.llm.sandbox import SandboxInput
    from zrb.llm.tool_call.ui_protocol import UIProtocol
    from zrb.llm.ui.ui_config import UIConfig


def _remove_first(items: list, item: Any) -> None:
    """Drop the first entry of *items* equal (or identical) to *item*, in place.

    A no-op when nothing matches — removal from an ordered collection never
    errors on a not-present item.
    """
    for index, existing in enumerate(items):
        if existing is item or existing == item:
            del items[index]
            return


class LLMChatTask(BaseTask):

    def __init__(
        self,
        name: str,
        *,
        color: int | None = None,
        icon: str | None = None,
        description: str | None = None,
        cli_only: bool = False,
        input: Sequence[AnyInput | None] | AnyInput | None = None,
        env: Sequence[AnyEnv | None] | AnyEnv | None = None,
        system_prompt: Callable[[AnyContext], str | fstring | None] | str | None = None,
        render_system_prompt: bool = False,
        prompt_manager: PromptManager | None = None,
        hook_manager: HookManager | None = None,
        active_skills: StrListAttr | None = None,
        render_active_skills: bool = True,
        tools: list[Tool | ToolFuncEither] | None = None,
        toolsets: list[AbstractToolset[None]] | None = None,
        tool_factories: (
            list[
                Callable[
                    [AnyContext],
                    Tool | ToolFuncEither | list[Tool | ToolFuncEither],
                ]
            ]
            | None
        ) = None,
        toolset_factories: (
            list[Callable[[AnyContext], AbstractToolset[None]]] | None
        ) = None,
        message: StrAttr | None = None,
        render_message: bool = True,
        attachment: (
            UserContent
            | list[UserContent]
            | Callable[[AnyContext], UserContent | list[UserContent]]
            | None
        ) = None,  # noqa
        history_processors: list[HistoryProcessor] | None = None,
        capabilities: "list[AbstractCapability[Any]] | None" = None,
        llm_limiter: LLMLimiter | None = None,
        model: (
            Callable[[AnyContext], Model | str | fstring | None] | Model | None
        ) = None,
        render_model: bool = True,
        model_settings: (
            ModelSettings | Callable[[AnyContext], ModelSettings] | None
        ) = None,
        model_getter: (
            "Callable[[str | Model | None], str | Model | None] | None"
        ) = None,
        model_renderer: (
            "Callable[[str | Model | None], str | Model | None] | None"
        ) = None,
        custom_model_names: StrListAttr | None = None,
        conversation_name: StrAttr | None = None,
        render_conversation_name: bool = True,
        history_manager: AnyHistoryManager | None = None,
        tool_confirmation: AnyToolConfirmation = None,
        permissions: "PermissionPolicyInput" = None,
        sandbox: "SandboxInput | BoolAttr" = None,
        yolo: BoolAttr = False,
        ui: UIProtocol | None = None,
        ui_factory: (
            Callable[
                [
                    AnyContext,
                    LLMTask,
                    AnyHistoryManager,
                    dict[str, list[str]],
                    Any,
                    str,
                    bool,
                    list[UserContent],
                ],
                UIProtocol,
            ]
            | None
        ) = None,
        approval_channel: ApprovalChannel | None = None,
        ui_config: "UIConfig | None" = None,
        custom_commands: (
            list[
                AnyCustomCommand
                | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
            ]
            | None
        ) = None,
        ui_greeting: StrAttr | None = None,
        render_ui_greeting: bool = True,
        ui_assistant_name: StrAttr | None = None,
        render_ui_assistant_name: bool = True,
        ui_jargon: StrAttr | None = None,
        render_ui_jargon: bool = True,
        ui_ascii_art: StrAttr | None = None,
        render_ui_ascii_art: bool = True,
        triggers: list[Callable[[], AsyncIterable[Any]]] | None = None,
        response_handlers: list[ResponseHandler] | None = None,
        tool_policies: list[ToolPolicy] | None = None,
        argument_formatters: list[ArgumentFormatter] | None = None,
        markdown_theme: "Theme | None" = None,
        enable_rewind: bool | None = None,
        snapshot_dir: StrAttr | None = None,
        include_default_ui: bool = True,
        interactive: BoolAttr = True,
        execute_condition: bool | str | Callable[[AnyContext], bool] = True,
        retries: int = 0,
        retry_period: float = 0,
        readiness_check: Sequence[AnyTask] | AnyTask | None = None,
        readiness_check_delay: float = 0.5,
        readiness_check_period: float = 5,
        readiness_failure_threshold: int = 1,
        readiness_timeout: int = 60,
        monitor_readiness: bool = False,
        upstream: Sequence[AnyTask] | AnyTask | None = None,
        fallback: Sequence[AnyTask] | AnyTask | None = None,
        successor: Sequence[AnyTask] | AnyTask | None = None,
        print_fn: PrintFn | None = None,
    ):
        """Define an interactive LLM chat session, as `zrb llm chat` does.

        Builds an inner `LLMTask` per turn and drives it through one or more UIs.
        For a single non-interactive prompt, use `LLMTask` directly.

        A `render_x` flag controls whether `x` is treated as an f-string template
        rendered against the task context. Set it False to pass a literal value
        containing braces.

        Args:
            message: Initial message to send before handing over to the user.
                Leave unset to start with an empty prompt.
            render_message: Whether to render `message` as a template.
            attachment: Images or files to send with the initial message.
            system_prompt: System prompt text, or a callable taking the context.
                Overrides whatever `prompt_manager` would compose.
            render_system_prompt: Whether to render `system_prompt` as a template.
                Off by default, since prompts commonly contain braces.
            prompt_manager: `PromptManager` composing the system prompt from
                sections. Defaults to the shared one.
            active_skills: Names of skills to pre-activate for the session.
            render_active_skills: Whether to render `active_skills` as templates.
            model: The model to use, as a name or a pydantic-ai `Model`. Defaults
                to `CFG.LLM_MODEL`.
            render_model: Whether to render `model` as a template.
            model_settings: Provider settings such as temperature.
            model_getter: Callable transforming the resolved base model into the
                active model (e.g. tier switching, A/B testing) — applied before
                `model_renderer`.
            model_renderer: Callable transforming the active model into the
                final pydantic-ai model (e.g. wrapping a tier name into a real
                model string).
            custom_model_names: Extra names offered by the model picker, beyond the
                detected ones.
            llm_limiter: Rate and token limiter. Defaults to the shared
                `llm_limiter`.
            capabilities: pydantic-ai capabilities to enable for the run.
            tools: Functions or `Tool`s the model may call.
            toolsets: Toolsets whose tools the model may call.
            tool_factories: Callables building tools per run from the context.
            toolset_factories: Callables building toolsets per run from the
                context.
            hook_manager: `HookManager` supplying lifecycle hooks. Unlike
                `LLMTask`, this defaults to a *fresh* manager per run rather
                than the global one, so one chat session's hooks cannot leak
                into the next. Pass the global `hook_manager` (or any specific
                one) to opt out of that isolation; `append_hook_factory` is the
                lighter option when you only need to register hooks.
            tool_confirmation: Policy deciding which tool calls need approval.
            tool_policies: Callables deciding whether a call is allowed, denied, or
                needs confirmation. The first to return a verdict decides.
            response_handlers: Callables post-processing a tool result before the
                model sees it. The first non-`None` result wins.
            argument_formatters: Callables controlling how tool-call arguments are
                displayed. All run in order, each overwriting the last.
            approval_channel: Channel carrying approval requests to whoever answers
                them.
            permissions: Policy bounding which files and commands tools may touch.
            sandbox: Whether, and how, tool calls run sandboxed.
            yolo: Skip tool confirmation. True for all tools, or a comma-separated
                string or set naming the tools to auto-approve.
            ui_config: Slash-command aliases and other UI-backend settings
                (`UIConfig`) — the xcom key yolo mode toggles through, whether the
                model picker lists Ollama/pydantic-ai models, and one field per
                command family. Each field left unset keeps its `CFG` default.
            conversation_name: Name the conversation is stored under.
            render_conversation_name: Whether to render `conversation_name` as a
                template.
            history_manager: Store persisting conversation history across runs.
            history_processors: Callables rewriting history before each request,
                run in order.
            enable_rewind: Whether the session can roll back to an earlier turn.
                Defaults to the config setting.
            snapshot_dir: Directory holding rewind snapshots. Defaults to the
                standard location under the git root.
            ui: A ready-made UI to drive the session with.
            ui_factory: Callable building the UI once the run's context is known.
                Prefer this over `ui` when the UI depends on resolved inputs.
            include_default_ui: Whether to attach the built-in terminal UI
                alongside any supplied one.
            interactive: Whether the session prompts the user. Set False to run
                `message` and exit.
            custom_commands: Extra slash commands, as `AnyCustomCommand`s or
                callables returning them.
            ui_greeting: Text shown when the session starts.
            render_ui_greeting: Whether to render `ui_greeting` as a template.
            ui_assistant_name: Name the assistant is labelled with.
            render_ui_assistant_name: Whether to render `ui_assistant_name` as a
                template.
            ui_ascii_art: Banner art shown above the greeting.
            render_ui_ascii_art: Whether to render `ui_ascii_art` as a template.
            ui_jargon: Tagline shown beside the banner.
            render_ui_jargon: Whether to render `ui_jargon` as a template.
            markdown_theme: Rich theme used to render the assistant's markdown.
            triggers: Callables returning async iterables whose items are submitted
                as user turns, letting an external source drive the session.

        Every parameter `BaseTask` accepts is also accepted here and behaves
        identically; see `BaseTask` for those.
        """
        super().__init__(
            name=name,
            color=color,
            icon=icon,
            description=description,
            cli_only=cli_only,
            input=input,
            env=env,
            execute_condition=execute_condition,
            retries=retries,
            retry_period=retry_period,
            readiness_check=readiness_check,
            readiness_check_delay=readiness_check_delay,
            readiness_check_period=readiness_check_period,
            readiness_failure_threshold=readiness_failure_threshold,
            readiness_timeout=readiness_timeout,
            monitor_readiness=monitor_readiness,
            upstream=upstream,
            fallback=fallback,
            successor=successor,
            print_fn=print_fn,
        )
        self._llm_limiter = llm_limiter
        if prompt_manager is None:
            prompt_manager = PromptManager(
                prompts=[system_prompt] if system_prompt else None,
                render=render_system_prompt,
                active_skills=active_skills,
                render_active_skills=render_active_skills,
                include_sections=[],
            )
        self._prompt_manager = prompt_manager
        self._system_prompt = system_prompt
        self._render_system_prompt = render_system_prompt
        self._active_skills = active_skills
        self._render_active_skills = render_active_skills
        self._tools = tools or []
        self._toolsets = toolsets or []
        # LLMChatTask-specific factories that resolve using parent context
        self._tool_factories = tool_factories or []
        self._toolset_factories = toolset_factories or []
        self._hook_factories: list[Callable[[HookManager], None]] = []
        # None (the default) means "a fresh manager per run" — see
        # `hook_manager` in the docstring for why chat isolates by default.
        self._hook_manager = hook_manager
        # Set per execution in _create_llm_task_core; the interactive teardown
        # fires the terminal SESSION_END on it.
        self._active_hook_manager: HookManager | None = None
        self._message = message
        self._render_message = render_message
        self._attachment = attachment
        self._history_processors = history_processors or []
        self._capabilities = capabilities or []
        self._model = model
        self._render_model = render_model
        self._model_settings = model_settings
        self._model_getter = model_getter
        self._model_renderer = model_renderer
        self._custom_model_names = custom_model_names
        self._conversation_name = conversation_name
        self._render_conversation_name = render_conversation_name
        self._history_manager = history_manager
        self._tool_confirmation = tool_confirmation
        self._uis: list["UIProtocol"] = []
        if ui is not None:
            self._uis.append(ui)
        self._ui_factories: list[Callable[..., "UIProtocol"]] = []
        if ui_factory is not None:
            self._ui_factories.append(ui_factory)
        self._approval_channels: list["ApprovalChannel"] = []
        if approval_channel is not None:
            self._approval_channels.append(approval_channel)
        self._permissions = permissions
        self._sandbox = sandbox
        self._yolo = yolo
        # Materialized lazily (see the `ui_config` property) — constructing a
        # UIConfig imports zrb.llm.ui, which transitively loads pydantic_ai,
        # prompt_toolkit, pdfplumber and playwright; the built-in `llm_chat`
        # task is built at `import zrb` time, so doing this eagerly here would
        # put that whole cost on every `import zrb`, not just chat sessions
        # that actually build a UI.
        self._ui_config = ui_config
        self._custom_commands = custom_commands or []
        # (value, render) per UI text; ChatRunning renders the block as one.
        self._ui_texts: dict[str, tuple[StrAttr | None, bool]] = {
            "greeting": (ui_greeting, render_ui_greeting),
            "assistant_name": (ui_assistant_name, render_ui_assistant_name),
            "ascii_art": (ui_ascii_art, render_ui_ascii_art),
            "jargon": (ui_jargon, render_ui_jargon),
        }
        self._triggers = triggers or []
        self._response_handlers = response_handlers or []
        self._tool_policies = tool_policies or []
        self._argument_formatters = (argument_formatters or []) + [
            replace_in_file_formatter,
            write_file_formatter,
        ]
        self._markdown_theme = markdown_theme
        self._enable_rewind = enable_rewind
        self._snapshot_dir = snapshot_dir
        self._include_default_ui = include_default_ui
        self._interactive = interactive
        self._running = ChatRunning(self)
        self._execution = ChatExecution(self)

    # --- Post-construction configuration (builder-style mutators) ------------
    # These mutate this task's own fields directly.
    # the state below is this task's own construction-time
    # data, and a class method mutating its own field needs no collaborator.

    @property
    def prompt_manager(self) -> PromptManager:
        """The `PromptManager` composing this task's system prompt.

        The constructor always builds a default one when none is passed in.
        """
        return self._prompt_manager

    @prompt_manager.setter
    def prompt_manager(self, value: PromptManager) -> None:
        """Replace the prompt manager wholesale."""
        if not isinstance(value, PromptManager):
            raise TypeError(
                f"{self.name}.prompt_manager must be a PromptManager, "
                f"got {type(value).__name__}."
            )
        self._prompt_manager = value

    # UIs (ordered) -----------------------------------------------------------

    def append_ui(self, ui: "UIProtocol") -> None:
        """Append a UI, keeping those already attached."""
        self._uis.append(ui)

    def prepend_ui(self, ui: "UIProtocol") -> None:
        """Attach *ui* ahead of those already attached."""
        self._uis.insert(0, ui)

    def set_uis(self, uis: "list[UIProtocol]") -> None:
        """Replace every attached UI wholesale."""
        self._uis = list(uis)

    def remove_ui(self, ui: "UIProtocol") -> None:
        """Detach *ui*. A no-op if it is not attached."""
        _remove_first(self._uis, ui)

    # UI factories (ordered) ---------------------------------------------------

    def append_ui_factory(self, factory: "Callable[..., UIProtocol]") -> None:
        """Append a factory building a UI once the run's context is known."""
        self._ui_factories.append(factory)

    def prepend_ui_factory(self, factory: "Callable[..., UIProtocol]") -> None:
        """Add *factory* ahead of those already registered."""
        self._ui_factories.insert(0, factory)

    def remove_ui_factory(self, factory: "Callable[..., UIProtocol]") -> None:
        """Drop *factory*. A no-op if it is not registered."""
        _remove_first(self._ui_factories, factory)

    @property
    def custom_model_names(self) -> StrListAttr | None:
        """Extra model names offered by the `/model` picker, beyond detected ones."""
        return self._custom_model_names

    @custom_model_names.setter
    def custom_model_names(self, value: StrListAttr | None) -> None:
        """Replace the custom model-name list."""
        self._custom_model_names = value

    # Approval channels (ordered) -----------------------------------------------

    def append_approval_channel(self, channel: "ApprovalChannel") -> None:
        """Append an approval channel to the list."""
        self._approval_channels.append(channel)

    def prepend_approval_channel(self, channel: "ApprovalChannel") -> None:
        """Add *channel* ahead of those already registered."""
        self._approval_channels.insert(0, channel)

    def remove_approval_channel(self, channel: "ApprovalChannel") -> None:
        """Drop *channel*. A no-op if it is not registered."""
        _remove_first(self._approval_channels, channel)

    # Toolsets (ordered) --------------------------------------------------------

    def append_toolset(self, *toolset: "AbstractToolset[None]") -> None:
        """Add pydantic-ai toolsets whose tools the agent may call."""
        self._toolsets += list(toolset)

    def prepend_toolset(self, *toolset: "AbstractToolset[None]") -> None:
        """Add toolsets ahead of those already registered."""
        self._toolsets[0:0] = toolset

    def set_toolsets(self, toolsets: "list[AbstractToolset[None]]") -> None:
        """Replace the toolset list wholesale."""
        self._toolsets = list(toolsets)

    def remove_toolset(self, toolset: "AbstractToolset[None]") -> None:
        """Drop *toolset*. A no-op if it is not registered."""
        _remove_first(self._toolsets, toolset)

    def append_toolset_factory(
        self, *factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ) -> None:
        """Add factories building toolsets per run, from the task context."""
        self._toolset_factories += list(factory)

    def prepend_toolset_factory(
        self, *factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ) -> None:
        """Add toolset factories ahead of those already registered."""
        self._toolset_factories[0:0] = factory

    def set_toolset_factories(
        self, factories: "list[Callable[[AnyContext], AbstractToolset[None]]]"
    ) -> None:
        """Replace the toolset-factory list wholesale."""
        self._toolset_factories = list(factories)

    def remove_toolset_factory(
        self, factory: "Callable[[AnyContext], AbstractToolset[None]]"
    ) -> None:
        """Drop *factory*. A no-op if it is not registered."""
        _remove_first(self._toolset_factories, factory)

    # Tools (ordered) -------------------------------------------------------

    def append_tool(self, *tool: "Tool | ToolFuncEither") -> None:
        """Add tools the agent may call."""
        self._tools += list(tool)

    def prepend_tool(self, *tool: "Tool | ToolFuncEither") -> None:
        """Add tools ahead of those already registered."""
        self._tools[0:0] = tool

    def set_tools(self, tools: "list[Tool | ToolFuncEither]") -> None:
        """Replace the tool list wholesale."""
        self._tools = list(tools)

    def remove_tool(self, tool: "Tool | ToolFuncEither") -> None:
        """Drop *tool*. A no-op if it is not registered."""
        _remove_first(self._tools, tool)

    def append_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ) -> None:
        """Add factories building tools per run, from the task context."""
        self._tool_factories += list(factory)

    def prepend_tool_factory(
        self,
        *factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ) -> None:
        """Add tool factories ahead of those already registered."""
        self._tool_factories[0:0] = factory

    def set_tool_factories(
        self,
        factories: "list[Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]]",
    ) -> None:
        """Replace the tool-factory list wholesale."""
        self._tool_factories = list(factories)

    def remove_tool_factory(
        self,
        factory: "Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]",
    ) -> None:
        """Drop *factory*. A no-op if it is not registered."""
        _remove_first(self._tool_factories, factory)

    # Hook factories (ordered) -----------------------------------------------

    def append_hook_factory(self, *factory: Callable[[HookManager], None]) -> None:
        """Add factories registering hooks on this task's hook manager."""
        self._hook_factories += list(factory)

    def prepend_hook_factory(self, *factory: Callable[[HookManager], None]) -> None:
        """Add hook factories ahead of those already registered."""
        self._hook_factories[0:0] = factory

    def set_hook_factories(
        self, factories: list[Callable[[HookManager], None]]
    ) -> None:
        """Replace the hook-factory list wholesale."""
        self._hook_factories = list(factories)

    def remove_hook_factory(self, factory: Callable[[HookManager], None]) -> None:
        """Drop *factory*. A no-op if it is not registered."""
        _remove_first(self._hook_factories, factory)

    # History processors (ordered) -------------------------------------------

    def append_history_processor(self, *processor: "HistoryProcessor") -> None:
        """Add processors that rewrite conversation history before each request."""
        self._history_processors += list(processor)

    def prepend_history_processor(self, *processor: "HistoryProcessor") -> None:
        """Add processors ahead of those already registered."""
        self._history_processors[0:0] = processor

    def set_history_processors(self, processors: "list[HistoryProcessor]") -> None:
        """Replace the history-processor list wholesale."""
        self._history_processors = list(processors)

    def remove_history_processor(self, processor: "HistoryProcessor") -> None:
        """Drop *processor*. A no-op if it is not registered."""
        _remove_first(self._history_processors, processor)

    # Response handlers (ordered) --------------------------------------------

    def append_response_handler(self, *handler: ResponseHandler) -> None:
        """Add handlers after those already registered."""
        self._response_handlers += list(handler)

    def prepend_response_handler(self, *handler: ResponseHandler) -> None:
        """Add handlers that post-process a tool's result before the model sees it."""
        self._response_handlers = list(handler) + self._response_handlers

    def set_response_handlers(self, handlers: list[ResponseHandler]) -> None:
        """Replace the response-handler list wholesale."""
        self._response_handlers = list(handlers)

    def remove_response_handler(self, handler: ResponseHandler) -> None:
        """Drop *handler*. A no-op if it is not registered."""
        _remove_first(self._response_handlers, handler)

    # Tool policies (ordered) -------------------------------------------------

    def append_tool_policy(self, *policy: ToolPolicy) -> None:
        """Add policies after those already registered."""
        self._tool_policies += list(policy)

    def prepend_tool_policy(self, *policy: ToolPolicy) -> None:
        """Add policies deciding whether a tool call is allowed, denied, or confirmed."""
        self._tool_policies = list(policy) + self._tool_policies

    def set_tool_policies(self, policies: list[ToolPolicy]) -> None:
        """Replace the tool-policy list wholesale."""
        self._tool_policies = list(policies)

    def remove_tool_policy(self, policy: ToolPolicy) -> None:
        """Drop *policy*. A no-op if it is not registered."""
        _remove_first(self._tool_policies, policy)

    # Argument formatters (ordered) -------------------------------------------

    def append_argument_formatter(self, *formatter: ArgumentFormatter) -> None:
        """Add formatters after those already registered."""
        self._argument_formatters += list(formatter)

    def prepend_argument_formatter(self, *formatter: ArgumentFormatter) -> None:
        """Add formatters controlling how a tool call's arguments are displayed."""
        self._argument_formatters = list(formatter) + self._argument_formatters

    def set_argument_formatters(self, formatters: list[ArgumentFormatter]) -> None:
        """Replace the argument-formatter list wholesale."""
        self._argument_formatters = list(formatters)

    def remove_argument_formatter(self, formatter: ArgumentFormatter) -> None:
        """Drop *formatter*. A no-op if it is not registered."""
        _remove_first(self._argument_formatters, formatter)

    # Triggers (ordered) ------------------------------------------------------

    def append_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]) -> None:
        """Add sources that feed messages into the chat loop unprompted."""
        self._triggers += trigger

    def prepend_trigger(self, *trigger: Callable[[], AsyncIterable[Any]]) -> None:
        """Add triggers ahead of those already registered."""
        self._triggers[0:0] = trigger

    def set_triggers(self, triggers: list[Callable[[], AsyncIterable[Any]]]) -> None:
        """Replace the trigger list wholesale."""
        self._triggers = list(triggers)

    def remove_trigger(self, trigger: Callable[[], AsyncIterable[Any]]) -> None:
        """Drop *trigger*. A no-op if it is not registered."""
        _remove_first(self._triggers, trigger)

    # Custom commands (ordered) ------------------------------------------------

    def append_custom_command(
        self,
        *custom_command: (
            AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
        ),
    ) -> None:
        """Add slash commands available inside the chat session."""
        self._custom_commands += list(custom_command)

    def prepend_custom_command(
        self,
        *custom_command: (
            AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
        ),
    ) -> None:
        """Add custom commands ahead of those already registered."""
        self._custom_commands[0:0] = custom_command

    def set_custom_commands(
        self,
        custom_commands: (
            "list[AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]]"
        ),
    ) -> None:
        """Replace the custom-command list wholesale."""
        self._custom_commands = list(custom_commands)

    def remove_custom_command(
        self,
        custom_command: (
            AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]
        ),
    ) -> None:
        """Drop *custom_command*. A no-op if it is not registered."""
        _remove_first(self._custom_commands, custom_command)

    # --- Construction-time config (own fields, read/written directly) -------

    @property
    def model_getter(
        self,
    ) -> "Callable[[str | Model | None], str | Model | None] | None":
        """Callable transforming the resolved base model into the active
        model (e.g. tier switching, A/B testing) — applied before
        `model_renderer`."""
        return self._model_getter

    @model_getter.setter
    def model_getter(
        self, value: "Callable[[str | Model | None], str | Model | None] | None"
    ) -> None:
        """Replace the model-getter hook, or None to remove it."""
        if value is not None and not callable(value):
            raise TypeError(
                f"{self.name}.model_getter must be a callable or None, "
                f"got {type(value).__name__}."
            )
        self._model_getter = value

    @property
    def model_renderer(
        self,
    ) -> "Callable[[str | Model | None], str | Model | None] | None":
        """Callable transforming the active model into the final
        pydantic-ai model — applied after `model_getter`."""
        return self._model_renderer

    @model_renderer.setter
    def model_renderer(
        self, value: "Callable[[str | Model | None], str | Model | None] | None"
    ) -> None:
        """Replace the model-renderer hook, or None to remove it."""
        if value is not None and not callable(value):
            raise TypeError(
                f"{self.name}.model_renderer must be a callable or None, "
                f"got {type(value).__name__}."
            )
        self._model_renderer = value

    @property
    def llm_limiter(self) -> "LLMLimiter | None":
        """Rate and token limiter throttling requests, or None if unlimited."""
        return self._llm_limiter

    @llm_limiter.setter
    def llm_limiter(self, value: "LLMLimiter | None") -> None:
        """Replace the rate/token limiter, or None to remove it."""
        if value is not None and not isinstance(value, LLMLimiter):
            raise TypeError(
                f"{self.name}.llm_limiter must be an LLMLimiter or None, "
                f"got {type(value).__name__}."
            )
        self._llm_limiter = value

    @property
    def permissions(self) -> "PermissionPolicyInput":
        """Policy bounding which files and commands the agent's tools may touch."""
        return self._permissions

    @permissions.setter
    def permissions(self, value: "PermissionPolicyInput") -> None:
        """Replace the permission policy.

        No `isinstance` guard: `PermissionPolicyInput` is deliberately a
        union of convenient shapes (`PermissionPolicy | str |
        Sequence[Rule | dict] | None`), not one concrete class — that
        flexibility is the design, not a gap.
        """
        self._permissions = value

    @property
    def sandbox(self) -> "SandboxInput | BoolAttr":
        """Whether, and how, tool calls run inside a sandbox."""
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: "SandboxInput | BoolAttr") -> None:
        """Replace the sandbox configuration.

        No `isinstance` guard: `SandboxInput` is deliberately a union
        (`SandboxPolicy | bool | None`), not one concrete class — that
        flexibility is the design, not a gap.
        """
        self._sandbox = value

    @property
    def history_manager(self) -> AnyHistoryManager | None:
        """Get the history manager."""
        return self._history_manager

    @history_manager.setter
    def history_manager(self, value: AnyHistoryManager | None) -> None:
        """Set the history manager, or None for the default file-backed store."""
        if value is not None and not isinstance(value, AnyHistoryManager):
            raise TypeError(
                f"{self.name}.history_manager must be an AnyHistoryManager or "
                f"None, got {type(value).__name__}. Subclass "
                f"zrb.llm.history_manager.any_history_manager.AnyHistoryManager."
            )
        self._history_manager = value

    @property
    def history_config(self) -> HistoryConfig:
        """The history-manager/conversation-name knobs as one group — see
        `HistoryConfig`. Recomputed on each read (not cached at construction)
        so `history_manager`'s public setter stays immediately visible here,
        matching that property's own contract."""
        return HistoryConfig(
            history_manager=self._history_manager,
            conversation_name=self._conversation_name,
            render_conversation_name=self._render_conversation_name,
        )

    @property
    def ui_factories(self) -> "list[Callable[..., UIProtocol]]":
        """Get the UI factories."""
        return self._ui_factories

    @ui_factories.setter
    def ui_factories(self, value: "list[Callable[..., UIProtocol]]") -> None:
        """Set the UI factories."""
        self._ui_factories = value

    @property
    def approval_channels(self) -> "list[ApprovalChannel]":
        """Get the approval channels."""
        return self._approval_channels

    @approval_channels.setter
    def approval_channels(self, value: "list[ApprovalChannel]") -> None:
        """Set the approval channels."""
        self._approval_channels = value

    @property
    def include_default_ui(self) -> bool:
        """Check if the default UI should be included."""
        return self._include_default_ui

    @include_default_ui.setter
    def include_default_ui(self, value: bool) -> None:
        """Set if the default UI should be included."""
        self._include_default_ui = value

    @property
    def uis(self) -> "list[UIProtocol]":
        """The UI protocol(s) attached so far."""
        return self._uis

    @property
    def hook_manager(self) -> "HookManager | None":
        """The `HookManager` passed at construction, or None for "fresh per run"."""
        return self._hook_manager

    @hook_manager.setter
    def hook_manager(self, value: "HookManager | None") -> None:
        """Replace the hook manager, or None to go back to "fresh per run"."""
        if value is not None and not isinstance(value, HookManager):
            raise TypeError(
                f"{self.name}.hook_manager must be a HookManager or None, "
                f"got {type(value).__name__}."
            )
        self._hook_manager = value

    @property
    def active_hook_manager(self) -> "HookManager | None":
        """The `HookManager` created for the run currently in flight, if any."""
        return self._active_hook_manager

    @active_hook_manager.setter
    def active_hook_manager(self, value: "HookManager | None") -> None:
        """Record the `HookManager` a run just created, for teardown to reach."""
        self._active_hook_manager = value

    @property
    def yolo(self) -> BoolAttr:
        """The raw `yolo` attribute (unevaluated bool/template/callable)."""
        return self._yolo

    @property
    def system_prompt(self):
        """The raw `system_prompt` attribute."""
        return self._system_prompt

    @property
    def render_system_prompt(self) -> bool:
        """Whether `system_prompt` is rendered as a template."""
        return self._render_system_prompt

    @property
    def active_skills(self) -> "StrListAttr | None":
        """Names of skills pre-activated for the session."""
        return self._active_skills

    @property
    def render_active_skills(self) -> bool:
        """Whether `active_skills` is rendered as templates."""
        return self._render_active_skills

    @property
    def message(self) -> "StrAttr | None":
        """The raw initial-message attribute."""
        return self._message

    @property
    def render_message(self) -> bool:
        """Whether `message` is rendered as a template."""
        return self._render_message

    @property
    def attachment(self):
        """The raw initial-attachment attribute."""
        return self._attachment

    @property
    def interactive(self) -> BoolAttr:
        """The raw `interactive` attribute."""
        return self._interactive

    @property
    def enable_rewind(self) -> bool | None:
        """Whether the session can roll back to an earlier turn, or None for the config default."""
        return self._enable_rewind

    @property
    def snapshot_dir(self) -> "StrAttr | None":
        """The raw rewind-snapshot-directory attribute."""
        return self._snapshot_dir

    @property
    def capabilities(self) -> "list[AbstractCapability[Any]]":
        """pydantic-ai capabilities enabled for the run."""
        return self._capabilities

    @property
    def conversation_name(self) -> "StrAttr | None":
        """The raw `conversation_name` attribute."""
        return self._conversation_name

    @property
    def render_conversation_name(self) -> bool:
        """Whether `conversation_name` is rendered as a template."""
        return self._render_conversation_name

    @property
    def model(self):
        """The raw `model` attribute."""
        return self._model

    @property
    def render_model(self) -> bool:
        """Whether `model` is rendered as a template."""
        return self._render_model

    @property
    def model_settings(self):
        """The raw `model_settings` attribute."""
        return self._model_settings

    @property
    def ui_config(self) -> "UIConfig":
        """Slash-command aliases and other UI-backend settings this task
        builds its UI with. Materialized lazily on first read — see the
        `__init__` comment on `self._ui_config` for why."""
        if self._ui_config is None:
            # lazy: zrb.llm.ui.ui_config transitively loads pydantic_ai,
            # prompt_toolkit, pdfplumber and playwright, via its package
            # __init__.
            from zrb.llm.ui.ui_config import UIConfig

            self._ui_config = UIConfig()
        return self._ui_config

    @ui_config.setter
    def ui_config(self, value: "UIConfig") -> None:
        """Replace the UI config wholesale."""
        # lazy: zrb.llm.ui.ui_config transitively loads pydantic_ai,
        # prompt_toolkit, pdfplumber and playwright, via its package __init__
        # — but a caller assigning a UIConfig instance has necessarily
        # already imported it themselves, so this costs nothing extra here.
        from zrb.llm.ui.ui_config import UIConfig

        if not isinstance(value, UIConfig):
            raise TypeError(
                f"{self.name}.ui_config must be a UIConfig, "
                f"got {type(value).__name__}."
            )
        self._ui_config = value

    @property
    def ui_texts(self) -> "dict[str, tuple[StrAttr | None, bool]]":
        """(value, render) per UI text block (greeting, assistant_name, ...)."""
        return self._ui_texts

    @property
    def markdown_theme(self) -> "Theme | None":
        """Rich theme used to render the assistant's markdown."""
        return self._markdown_theme

    @markdown_theme.setter
    def markdown_theme(self, value: "Theme | None") -> None:
        """Replace the markdown theme, or None for the default.

        No `isinstance` guard here (unlike the other slots): `rich.theme.Theme`
        is only imported under `TYPE_CHECKING` — every module that touches it
        does the same — so validating against the real class would force an
        eager `rich` import (~12ms) on every `import zrb`. The type hint is
        the only guard.
        """
        self._markdown_theme = value

    @property
    def tool_confirmation(self) -> AnyToolConfirmation:
        """Policy deciding which tool calls need approval."""
        return self._tool_confirmation

    @property
    def tools(self) -> "list[Tool | ToolFuncEither]":
        """Tools registered directly (not via a factory)."""
        return self._tools

    @property
    def toolsets(self) -> "list[AbstractToolset[None]]":
        """Toolsets registered directly (not via a factory)."""
        return self._toolsets

    @property
    def tool_factories(
        self,
    ) -> "list[Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]]":
        """Factories building tools per run, from the task context."""
        return self._tool_factories

    @property
    def toolset_factories(
        self,
    ) -> "list[Callable[[AnyContext], AbstractToolset[None]]]":
        """Factories building toolsets per run, from the task context."""
        return self._toolset_factories

    @property
    def hook_factories(self) -> list[Callable[[HookManager], None]]:
        """Factories registering hooks on the run's `HookManager`."""
        return self._hook_factories

    @property
    def history_processors(self) -> "list[HistoryProcessor]":
        """Processors rewriting conversation history before each request."""
        return self._history_processors

    @property
    def response_handlers(self) -> list[ResponseHandler]:
        """Handlers post-processing a tool's result before the model sees it."""
        return self._response_handlers

    @property
    def tool_policies(self) -> list[ToolPolicy]:
        """Policies deciding whether a tool call is allowed, denied, or confirmed."""
        return self._tool_policies

    @property
    def argument_formatters(self) -> list[ArgumentFormatter]:
        """Formatters controlling how a tool call's arguments are displayed."""
        return self._argument_formatters

    @property
    def triggers(self) -> "list[Callable[[], AsyncIterable[Any]]]":
        """Sources feeding unprompted messages into the chat loop."""
        return self._triggers

    @property
    def custom_commands(
        self,
    ) -> "list[AnyCustomCommand | Callable[[], AnyCustomCommand | list[AnyCustomCommand]]]":
        """Extra slash commands available inside the chat session."""
        return self._custom_commands

    # --- ChatRunning delegators (cross-part call sites only) -----------------

    async def run_non_interactive_session(self, *args: Any, **kwargs: Any) -> Any:
        """Run a non-interactive (one-shot) chat session."""
        return await self._running.run_non_interactive_session(*args, **kwargs)

    async def run_interactive_session(self, *args: Any, **kwargs: Any) -> Any:
        """Run an interactive chat session with a UI."""
        return await self._running.run_interactive_session(*args, **kwargs)

    # --- ChatExecution delegators ---------------------------------------------

    def get_system_prompt(self, ctx: AnyContext) -> str:
        """Compose the full system prompt for this run."""
        return self._execution.get_system_prompt(ctx)

    async def _exec_action(self, ctx: AnyContext) -> Any:
        return await self._execution.exec_action(ctx)

    async def teardown_interactive_resources(self) -> None:
        """Release process-global resources when an interactive chat ends."""
        await self._execution.teardown_interactive_resources()

    async def teardown_background_hooks(self) -> None:
        """Settle this run's detached (``async: true``) hooks."""
        await self._execution.teardown_background_hooks()

    def get_all_tools(self, ctx: AnyContext) -> "list[Tool | ToolFuncEither]":
        """Get all tools including those resolved from factories using parent context."""
        return self._execution.get_all_tools(ctx)

    def get_all_toolsets(self, ctx: AnyContext) -> "list[AbstractToolset[None]]":
        """Get all toolsets including those resolved from factories using parent context."""
        return self._execution.get_all_toolsets(ctx)

    def get_model(self, ctx: AnyContext) -> "str | Model":
        """Resolve the model to use for this run."""
        return self._execution.get_model(ctx)

    def get_ui_conversation_name(
        self, ui: "UIProtocol", initial_conversation_name: str
    ) -> str:
        """Get the current conversation name from UI or fallback to initial name."""
        return self._execution.get_ui_conversation_name(ui, initial_conversation_name)
