"""Execution + resource methods for `LLMChatTask`.

Holds the runtime entrypoint (`exec_action`), system-prompt composition, the
inner `LLMTask` construction, tool/toolset/UI-command resolution,
conversation-name and model helpers, and the session-end teardown.

Composed into `LLMChatTask` as `self._execution`; reads and writes the owner's
state through `self._llm_chat_task`. The session runners live in the sibling
`ChatRunning` part and are reached through the owner's delegators.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING, Any, Callable, cast

from zrb.attr.tpl import Tpl
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.env.any_env import AnyEnv
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.approval import resolve_approval_channel
from zrb.llm.history_manager.file_history_manager import default_history_manager
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.lsp.manager import lsp_manager
from zrb.llm.permission import tool_capability
from zrb.llm.sandbox import coerce_sandbox
from zrb.llm.summarizer import create_summarizer_history_processor
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.task.shared_getters import (
    get_policy_skip_decision,
    resolve_all_tools,
    resolve_all_toolsets,
    resolve_conversation_name,
    resolve_model,
    resolve_system_prompt,
)
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.std_ui import StdUI
from zrb.llm.util.attachment import get_attachments
from zrb.util.attr import get_attr, get_bool_attr, get_str_attr
from zrb.util.cli.style import stylize_highlight, stylize_muted
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from zrb.llm.agent import AnyToolConfirmation
    from zrb.llm.agent.types import (
        AbstractCapability,
        AbstractToolset,
        Model,
        Tool,
        ToolFuncEither,
    )
    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.sandbox import SandboxPolicy
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.history_config import HistoryConfig
    from zrb.llm.ui.any_ui import AnyUI


def parse_yolo_value(value: Any) -> "bool | frozenset[str]":
    """Parse a yolo input value into bool or frozenset of tool names.

    - bool True/False → returned as-is
    - "true"/"1"/"yes" → True (full yolo)
    - ""/"false"/"0"/"no" → False (no yolo)
    - "Write,Edit" → frozenset({"Write", "Edit"}) (selective yolo)
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (set, frozenset)):
        return frozenset(value)
    if not value:
        return False
    s = str(value).strip()
    if not s or s.lower() in ("false", "0", "no", "none"):
        return False
    if s.lower() in ("true", "1", "yes"):
        return True
    tools = frozenset(t.strip() for t in s.split(",") if t.strip())
    return tools if tools else False


@dataclass(frozen=True)
class _InnerTaskResolution:
    """Values `_create_llm_task_core` needs, computed by `_resolve_inner_task_config`.

    Separates resolution (reading owner state, coercing sandbox/approval/hook
    values, building the approval predicate) from the `LLMTask(...)` call.
    """

    tool_confirmation: "AnyToolConfirmation"
    ui: "AnyUI | None"
    approval_channel: "AnyApprovalChannel | None"
    hook_manager: HookManager
    sandbox: "SandboxPolicy | None"
    history: "HistoryConfig"
    should_skip_approval: Callable[..., bool]


class ChatExecution:
    """Execution + resource lifecycle for LLMChatTask."""

    def __init__(self, llm_chat_task: "LLMChatTask") -> None:
        self._llm_chat_task = llm_chat_task

    def get_system_prompt(self, ctx: AnyContext) -> str:
        """Compose the full system prompt for this run."""
        return resolve_system_prompt(ctx, self._llm_chat_task.prompt_manager)

    async def exec_action(self, ctx: AnyContext) -> Any:
        initial_conversation_name = self._get_initial_conversation_name(ctx)
        raw_yolo = get_attr(ctx, self._llm_chat_task.yolo, "")
        initial_yolo = parse_yolo_value(raw_yolo)
        yolo_xcom_key = self._llm_chat_task.ui_config.yolo_xcom_key
        if yolo_xcom_key not in ctx.xcom:
            ctx.xcom[yolo_xcom_key] = Xcom()
        ctx.xcom[yolo_xcom_key].set(initial_yolo)

        initial_message = get_attr(ctx, self._llm_chat_task.message, "")
        initial_attachments = get_attachments(ctx, self._llm_chat_task.attachment)
        interactive = get_bool_attr(ctx, self._llm_chat_task.interactive, True)
        history_manager = (
            default_history_manager()
            if self._llm_chat_task.history_manager is None
            else self._llm_chat_task.history_manager
        )

        effective_enable_rewind = (
            CFG.LLM_ENABLE_REWIND
            if self._llm_chat_task.enable_rewind is None
            else self._llm_chat_task.enable_rewind
        )
        effective_snapshot_dir = get_str_attr(
            ctx, self._llm_chat_task.snapshot_dir, CFG.LLM_SNAPSHOT_DIR
        )

        ui_commands = self._get_ui_commands()

        # Resolved against the *parent* context, so a tool factory sees the
        # chat task's inputs rather than the inner task's.
        resolved_tools = self.get_all_tools(ctx)
        resolved_toolsets = self.get_all_toolsets(ctx)

        # Lets the system_context section surface model-specific notes. Re-set
        # on every exec because `/model` updates ctx.input.model.
        self._llm_chat_task.prompt_manager.model = self.get_model(ctx)

        llm_task_core = self._create_llm_task_core(
            ctx,
            ui_commands["summarize"],
            history_manager,
            interactive,
            resolved_tools,
            resolved_toolsets,
            self._llm_chat_task.capabilities,
        )

        if not interactive:
            try:
                return await self._llm_chat_task.run_non_interactive_session(
                    ctx=ctx,
                    llm_task_core=llm_task_core,
                    history_manager=history_manager,
                    ui_commands=ui_commands,
                    initial_message=initial_message,
                    initial_conversation_name=initial_conversation_name,
                    initial_yolo=initial_yolo,
                    initial_attachments=initial_attachments,
                )
            finally:
                await self.teardown_background_hooks()

        try:
            return await self._llm_chat_task.run_interactive_session(
                ctx=ctx,
                llm_task_core=llm_task_core,
                history_manager=history_manager,
                ui_commands=ui_commands,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
                enable_rewind=effective_enable_rewind,
                snapshot_dir=effective_snapshot_dir,
            )
        finally:
            await self.teardown_interactive_resources()

    async def teardown_interactive_resources(self) -> None:
        """Release process-global resources when an interactive chat ends.

        Runs on normal exit, ``/exit``, EOF, or Ctrl+C (the ``finally`` fires on
        ``KeyboardInterrupt``). Stops LSP language-server subprocesses gracefully
        while the event loop is still alive — the ``atexit`` backstops only run
        once the loop is gone, when graceful async shutdown is no longer possible.

        Gated to the interactive session on purpose: the non-interactive path is
        reused per-message by the web/SSE runner, where tearing servers down
        would restart them on every message. Each step is guarded so teardown
        never raises; a second ``KeyboardInterrupt`` still propagates.
        """
        # SESSION_END fires once per session, like Claude Code's SessionEnd
        # (run_agent fires only STOP per turn). Every exit cause funnels through
        # one `finally`, so `source` is Claude's catch-all "other".
        if self._llm_chat_task.active_hook_manager is not None:
            try:
                await self._llm_chat_task.active_hook_manager.execute_hooks(
                    HookEvent.SESSION_END,
                    {"reason": "exit"},
                    source="other",
                )
            except Exception:
                CFG.LOGGER.debug("SESSION_END hook raised at teardown", exc_info=True)

        try:
            await lsp_manager.shutdown_all()
        except Exception as e:
            CFG.LOGGER.debug(f"LSP shutdown at session end failed: {e}")
        # Settle detached hooks before releasing the worker pool, so their
        # cancellation handlers can kill process trees that sit in their own
        # process group and never see the terminal's Ctrl+C.
        await self.teardown_background_hooks()
        # Reap background shell / delegation subprocesses while the loop is
        # alive; otherwise their exit logs "Loop <...> that handles pid N is
        # closed".
        try:
            from zrb.llm.tool.shell_background import get_shell_background_registry

            await get_shell_background_registry().cancel_all()
        except Exception as e:
            CFG.LOGGER.debug(f"Background-shell teardown at session end failed: {e}")
        try:
            from zrb.llm.tool.delegate_background import get_background_registry

            get_background_registry().cancel_all()
        except Exception as e:
            CFG.LOGGER.debug(
                f"Background-delegation teardown at session end failed: {e}"
            )
        # lazy: zrb internal — only needed at teardown; keeps this import
        # off the hot path every other turn takes.
        try:
            from zrb.llm.hook.executor import shutdown_hook_executor

            shutdown_hook_executor(wait=False)
        except Exception as e:
            CFG.LOGGER.debug(f"Hook-executor shutdown at session end failed: {e}")

    async def teardown_background_hooks(self) -> None:
        """Settle this run's detached (``async: true``) hooks.

        Runs on both paths; the non-interactive path skips the rest of the
        teardown because the web/SSE runner reuses it per message. Detached
        hooks sit in their own process group, so nothing else reaps them.

        ``drain=True`` gives just-dispatched hooks (e.g. a Stop notifier) their
        grace period before cancelling stragglers; cancel-first would
        effectively disable async hooks for non-interactive callers.

        Shuts down this run's ``HookManager`` (built fresh per execution),
        falling back to the module singleton only when none was created —
        matching ``run_agent``'s ``hook_manager or default`` resolution.
        """
        try:
            if self._llm_chat_task.active_hook_manager is not None:
                await self._llm_chat_task.active_hook_manager.shutdown(drain=True)
            else:
                # lazy: zrb internal — only needed at teardown; keeps this
                # import off the hot path every other turn takes.
                from zrb.llm.hook.manager import hook_manager

                await hook_manager.shutdown(drain=True)
        except Exception as e:
            CFG.LOGGER.debug(f"Background-hook shutdown at teardown failed: {e}")

    def get_all_tools(self, ctx: AnyContext) -> list[Tool | ToolFuncEither]:
        """Get all tools including those resolved from factories using parent context."""
        return resolve_all_tools(
            ctx, self._llm_chat_task.tools, self._llm_chat_task.tool_factories
        )

    def get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories using parent context."""
        return resolve_all_toolsets(
            ctx, self._llm_chat_task.toolsets, self._llm_chat_task.toolset_factories
        )

    def _get_ui_commands(self) -> dict[str, list[str]]:
        """The task's UI slash-command aliases keyed by command name, the shape
        `UIConfig.merge_commands` expects. Each field is already resolved."""
        ui_config = self._llm_chat_task.ui_config
        return {
            field.name.removesuffix("_commands"): list(getattr(ui_config, field.name))
            for field in fields(ui_config)
            if field.name.endswith("_commands")
        }

    def _create_llm_task_core(
        self,
        ctx: AnyContext,
        summarize_commands: list[str],
        history_manager: AnyHistoryManager,
        interactive: bool,
        resolved_tools: list[Tool | ToolFuncEither],
        resolved_toolsets: list[AbstractToolset[None]],
        capabilities: "list[AbstractCapability[Any]]",
    ) -> LLMTask:
        """Create the inner LLMTask that handles the actual processing."""
        llm_chat_task = self._llm_chat_task
        resolved = self._resolve_inner_task_config(
            ctx, history_manager, interactive, resolved_tools
        )

        return LLMTask(
            name=f"{llm_chat_task.name}-process",
            # One `async_run` is one conversation turn, which is not safely
            # repeatable: tools have already run and been checkpointed to
            # history. Transient provider errors are retried per request by the
            # agent's retry_loop (CFG.LLM_API_MAX_RETRIES) instead.
            retries=0,
            input=[
                StrInput("message", "Message"),
                StrInput("session", "Conversation Session"),
                BoolInput("yolo", "YOLO Mode"),
                StrInput("attachments", "Attachments"),
                StrInput("model", "Model"),
            ],
            env=cast(list[AnyEnv | None], llm_chat_task.envs),
            system_prompt=llm_chat_task.system_prompt,
            prompt_manager=llm_chat_task.prompt_manager,
            active_skills=llm_chat_task.active_skills,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            history_processors=llm_chat_task.history_processors
            + [create_summarizer_history_processor()],
            capabilities=capabilities,
            llm_limiter=llm_chat_task.llm_limiter,
            history_manager=resolved.history.history_manager,
            hook_manager=resolved.hook_manager,
            tool_confirmation=resolved.tool_confirmation,
            ui=resolved.ui,
            approval_channel=resolved.approval_channel,
            permissions=llm_chat_task.permissions,
            sandbox=resolved.sandbox,
            message=Tpl("{ctx.input.message}"),
            conversation_name=resolved.history.conversation_name,
            yolo=Tpl("{ctx.input.yolo}"),
            dynamic_yolo=resolved.should_skip_approval,
            attachment=lambda ctx: ctx.input.attachments,
            model=lambda ctx: ctx.input.get("model"),
            model_settings=llm_chat_task.model_settings,
            model_getter=llm_chat_task.model_getter,
            model_renderer=llm_chat_task.model_renderer,
            summarize_commands=summarize_commands,
        )

    def _resolve_inner_task_config(
        self,
        ctx: AnyContext,
        history_manager: AnyHistoryManager,
        interactive: bool,
        resolved_tools: list[Tool | ToolFuncEither],
    ) -> "_InnerTaskResolution":
        """Resolve every value `_create_llm_task_core` needs but does not itself
        compute: tool-confirmation/UI mode, the approval channel, the per-run
        hook manager, sandbox coercion, and the wrap-boundary history override.
        """
        llm_chat_task = self._llm_chat_task
        tool_confirmation = llm_chat_task.tool_confirmation
        ui = llm_chat_task.uis if llm_chat_task.uis else None

        if interactive:
            # The interactive UI handles confirmation itself.
            tool_confirmation = None
            ui = None
        elif (
            llm_chat_task.tool_policies
            or llm_chat_task.response_handlers
            or llm_chat_task.argument_formatters
        ):
            if not ui and not llm_chat_task.ui_factories:
                ui = StdUI()
            tool_confirmation = ToolCallHandler(
                tool_policies=llm_chat_task.tool_policies,
                argument_formatters=llm_chat_task.argument_formatters,
                response_handlers=llm_chat_task.response_handlers,
            )
        elif not ui and not llm_chat_task.ui_factories:
            # With ui_factories, the non-interactive session attaches their UIs
            # (e.g. the web/SSE HTTPUI) instead of falling back to stdout.
            ui = StdUI()

        # Keyed by the LLM-visible tool name; consulted only under a policy.
        cap_by_name = {
            (getattr(t, "name", None) or getattr(t, "__name__", "")): tool_capability(t)
            for t in resolved_tools
        }

        _should_skip_approval = _make_should_skip_approval(
            ctx, llm_chat_task, cap_by_name
        )

        effective_approval_channel = resolve_approval_channel(
            llm_chat_task.approval_channels
        )

        CFG.LOGGER.debug("llm_chat_task _create_llm_task_core:")
        CFG.LOGGER.debug(f"  tool_confirmation: {tool_confirmation}")
        CFG.LOGGER.debug(f"  effective_approval_channel: {effective_approval_channel}")
        CFG.LOGGER.debug(f"  _approval_channels: {llm_chat_task.approval_channels}")

        hook_manager = (
            HookManager()
            if llm_chat_task.hook_manager is None
            else llm_chat_task.hook_manager
        )
        for factory in llm_chat_task.hook_factories:
            factory(hook_manager)
        # Teardown fires SESSION_END and drains hooks on this exact manager.
        llm_chat_task.active_hook_manager = hook_manager

        # Resolved against the outer context: the inner task's context has no
        # "sandbox" input.
        resolved_sandbox = coerce_sandbox(ctx, llm_chat_task.sandbox)

        # The inner task's conversation is always the active chat session.
        resolved_history = replace(
            llm_chat_task.history_config,
            history_manager=history_manager,
            conversation_name=Tpl("{ctx.input.session}"),
        )

        return _InnerTaskResolution(
            tool_confirmation=tool_confirmation,
            ui=cast("AnyUI | None", ui),
            approval_channel=effective_approval_channel,
            hook_manager=hook_manager,
            sandbox=resolved_sandbox,
            history=resolved_history,
            should_skip_approval=_should_skip_approval,
        )

    def _print_conversation_name(self, ctx: AnyContext, conversation_name: str):
        stylized_label = stylize_muted("Session")
        stylized_conversation_name = stylize_highlight(conversation_name)
        ctx.print(
            stylize_muted(f"{stylized_label}: {stylized_conversation_name}"), plain=True
        )

    def _get_initial_conversation_name(self, ctx: AnyContext) -> str:
        return resolve_conversation_name(ctx, self._llm_chat_task.conversation_name)

    def get_ui_conversation_name(
        self, ui: "AnyUI", initial_conversation_name: str
    ) -> str:
        """Get the current conversation name from UI or fallback to initial name."""
        if isinstance(ui, BaseUI):
            return ui.conversation_session_name
        return getattr(ui, "conversation_session_name", initial_conversation_name)

    def get_model(self, ctx: AnyContext) -> str | Model:
        """Resolve the model to use for this run.

        A `Tpl` or callable model attribute is resolved against `ctx`. An empty
        result falls back to `CFG.LLM_MODEL`.
        """
        return resolve_model(ctx, self._llm_chat_task.model)


def _make_should_skip_approval(ctx, llm_chat_task, cap_by_name):
    """Build the predicate that decides whether a tool call skips approval.

    Approval precedence chain:
      perm_policy: allow→auto-approve, deny→auto-approve (gate blocks),
                   ask→defer to tool_policy cascade
      tool_policy: handled in _resolve_approval (deferred_calls.py)
      yolo:        handled in _resolve_approval (deferred_calls.py)
    """

    def _should_skip_approval(tool_def=None):
        decision = get_policy_skip_decision(tool_def, cap_by_name)
        if decision is not None:
            return decision
        return _yolo_skip_decision(ctx, llm_chat_task, tool_def)

    return _should_skip_approval


def _yolo_skip_decision(ctx, llm_chat_task, tool_def) -> bool:
    """Whether YOLO mode covers this tool call.

    The xcom value is either a bool (all tools) or a frozenset of the tool
    names YOLO was granted for.
    """
    yolo_xcom_key = llm_chat_task.ui_config.yolo_xcom_key
    if yolo_xcom_key not in ctx.xcom:
        return False
    yolo_value = ctx.xcom[yolo_xcom_key].get(False)
    if isinstance(yolo_value, bool):
        return yolo_value
    if isinstance(yolo_value, frozenset) and tool_def is not None:
        return getattr(tool_def, "name", str(tool_def)) in yolo_value
    return False
