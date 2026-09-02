"""Execution + resource methods for `LLMChatTask`.

Holds the runtime entrypoint (`exec_action`), system-prompt composition, the
inner `LLMTask` construction (`_create_llm_task_core`), tool/toolset/UI-command
resolution, conversation-name helpers, model resolution, and the interactive
teardown that releases process-global resources at session end.

Kept separate from `task.py` (config-time `__init__`) and from
`building.py` / `running.py` because this part owns the
execution-time machinery that `BaseTask` invokes on the composed task.

Composed into `LLMChatTask` as `self._execution`: keeps `LLMChatTask` in
`self._llm_chat_task` and reads/writes its state through that reference. The
two session runners it calls (`run_interactive_session`,
`run_non_interactive_session`) are implemented by the sibling `ChatRunning`
collaborator and reached through `self._llm_chat_task`'s delegators — the same
way `self.name`, `self.envs` (`BaseTask` properties), and
`apply_common_tools` use the task object as a full `CommonToolHost`.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING, Any, Callable, cast

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
from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    get_effective_policy,
    tool_capability,
)
from zrb.llm.sandbox import coerce_sandbox
from zrb.llm.summarizer import create_summarizer_history_processor
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.task.shared_getters import (
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
    from zrb.llm.approval.approval_channel import ApprovalChannel
    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.sandbox import SandboxPolicy
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.history_config import HistoryConfig
    from zrb.llm.tool_call.ui_protocol import UIProtocol


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
    """Everything `_create_llm_task_core` needs to assemble the inner `LLMTask`
    call, computed once by `_resolve_inner_task_config`.

    Keeps resolution (reading `llm_chat_task` state, coercing sandbox/approval/
    hook-manager values, building the yolo/permission approval closure) separate
    from construction (the `LLMTask(...)` call itself), so each half can be read
    — and, if it ever needs one, tested — on its own.
    """

    tool_confirmation: "AnyToolConfirmation"
    ui: "UIProtocol | None"
    approval_channel: "ApprovalChannel | None"
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
        # 1. Resolve inputs/attributes
        initial_conversation_name = self._get_initial_conversation_name(ctx)
        raw_yolo = get_attr(ctx, self._llm_chat_task.yolo, "", True)
        initial_yolo = parse_yolo_value(raw_yolo)
        yolo_xcom_key = self._llm_chat_task.ui_config.yolo_xcom_key
        if yolo_xcom_key not in ctx.xcom:
            ctx.xcom[yolo_xcom_key] = Xcom()
        ctx.xcom[yolo_xcom_key].set(initial_yolo)

        initial_message = get_attr(
            ctx, self._llm_chat_task.message, "", self._llm_chat_task.render_message
        )
        initial_attachments = get_attachments(ctx, self._llm_chat_task.attachment)
        interactive = get_bool_attr(ctx, self._llm_chat_task.interactive, True)
        history_manager = (
            default_history_manager()
            if self._llm_chat_task.history_manager is None
            else self._llm_chat_task.history_manager
        )

        # 2. Resolve rewind settings
        effective_enable_rewind = (
            CFG.LLM_ENABLE_REWIND
            if self._llm_chat_task.enable_rewind is None
            else self._llm_chat_task.enable_rewind
        )
        effective_snapshot_dir = get_str_attr(
            ctx, self._llm_chat_task.snapshot_dir, CFG.LLM_SNAPSHOT_DIR, True
        )

        # 3. Resolve UI Commands
        ui_commands = self._get_ui_commands()

        # 4. Resolve tools/toolsets from factories using parent context
        resolved_tools = self.get_all_tools(ctx)
        resolved_toolsets = self.get_all_toolsets(ctx)

        # 4a. Wire the resolved model so the system_context section can surface
        # model-specific capability notes (e.g. lack of parallel tool-call
        # support). Re-set on every exec — `/model` switches update
        # ctx.input.model, which flows through get_model(ctx).
        self._llm_chat_task.prompt_manager.model = self.get_model(ctx)

        # 5. Create core LLM task
        llm_task_core = self._create_llm_task_core(
            ctx,
            ui_commands["summarize"],
            history_manager,
            interactive,
            resolved_tools,
            resolved_toolsets,
            self._llm_chat_task.capabilities,
        )

        # 6. Run Interactive or Non-Interactive
        # Note: AsyncExitStack for toolsets is handled by LLMTask._exec_action
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
        # Terminal SESSION_END: the interactive chat session is ending (normal
        # exit, /exit, EOF, or Ctrl+C). Claude Code fires SessionEnd once per
        # session, not per turn — run_agent fires only STOP per turn. Guarded so
        # a misbehaving hook never blocks resource teardown.
        #
        # `source` is the Claude-compatible matcher field for SessionEnd. This
        # single teardown point cannot distinguish the exit cause (normal /
        # /exit / EOF / Ctrl+C all funnel through the same `finally`) without
        # threading the reason through the chat loop, so we report the Claude
        # catch-all "other"; finer values (logout / prompt_input_exit) are a
        # follow-up. `reason` stays in event_data for the CLAUDE_* env vars.
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
        # Order matters: settle the detached async hooks first so their
        # cancellation handlers can kill their process trees, then release the
        # worker pool. Their subprocesses are in their own process group and so
        # never receive the terminal's Ctrl+C — this is what stops them
        # outliving the session.
        await self.teardown_background_hooks()
        # Kill background shell / delegation work and reap their subprocesses
        # while the loop is still alive. Anything left running when the loop
        # closes logs "Loop <...> that handles pid N is closed" the moment it
        # exits, because its exit event can no longer be delivered.
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

        Runs on *both* paths. The interactive session calls it as part of the
        full teardown; the non-interactive one calls it on its own, because the
        rest of that teardown (LSP servers, the worker pool) is deliberately
        skipped there — the web/SSE runner reuses that path per message. Without
        this, a one-shot ``zrb llm chat -m "..."`` left its detached hooks
        running after the process exited: they sit in their own process group,
        so nothing else reaps them.

        ``drain=True``: the pending hooks were very likely dispatched moments
        ago (a Stop-event notifier on the last turn), so give them their grace
        period to finish before cancelling the stragglers. Cancel-first is right
        at *session* end and wrong at *run* end — it would effectively disable
        async hooks for every non-interactive caller.

        Shuts down *this run's* manager: ``_create_llm_task_core`` builds a fresh
        ``HookManager`` per execution and that is the instance every hook ran on,
        so the module-level singleton holds none of this run's tasks. Falls back
        to the singleton only when no per-run manager was created, matching
        ``run_agent``'s own ``hook_manager or default`` resolution.
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
        """The task's UI slash-command aliases, as a dict — the shape
        `create_ui_factory`-built UIs expect (`UIConfig.merge_commands`).
        Each field already resolved the task's own override, else CFG, when
        `ui_config` was built/materialized, so there is nothing left to merge
        here."""
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

        # Pass resolved tools/toolsets to LLMTask (no factories needed since already resolved)
        return LLMTask(
            name=f"{llm_chat_task.name}-process",
            input=[
                StrInput("message", "Message"),
                StrInput("session", "Conversation Session"),
                BoolInput("yolo", "YOLO Mode"),
                StrInput("attachments", "Attachments"),
                StrInput("model", "Model"),
            ],
            env=cast(list[AnyEnv | None], llm_chat_task.envs),
            system_prompt=llm_chat_task.system_prompt,
            render_system_prompt=llm_chat_task.render_system_prompt,
            prompt_manager=llm_chat_task.prompt_manager,
            active_skills=llm_chat_task.active_skills,
            render_active_skills=llm_chat_task.render_active_skills,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            # No factories passed - tools/toolsets already resolved with parent context
            history_processors=llm_chat_task.history_processors
            + [create_summarizer_history_processor()],
            capabilities=capabilities,
            llm_config=llm_chat_task.llm_config,
            llm_limiter=llm_chat_task.llm_limiter,
            history_manager=resolved.history.history_manager,
            hook_manager=resolved.hook_manager,
            tool_confirmation=resolved.tool_confirmation,
            ui=resolved.ui,
            approval_channel=resolved.approval_channel,
            permissions=llm_chat_task.permissions,
            sandbox=resolved.sandbox,
            message="{ctx.input.message}",
            conversation_name=resolved.history.conversation_name,
            render_conversation_name=resolved.history.render_conversation_name,
            yolo="{ctx.input.yolo}",
            dynamic_yolo=resolved.should_skip_approval,
            attachment=lambda ctx: ctx.input.attachments,
            model=lambda ctx: ctx.input.get("model"),
            render_model=False,
            # Without this, LLMChatTask(model_settings=...) is accepted but
            # silently ignored: the inner task falls back to llm_config's.
            model_settings=llm_chat_task.model_settings,
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
            # Interactive mode: Let the UI handle everything
            tool_confirmation = None
            ui = None
        elif (
            llm_chat_task.tool_policies
            or llm_chat_task.response_handlers
            or llm_chat_task.argument_formatters
        ):
            # Non-interactive with policies/handlers/formatters: Use ToolCallHandler
            if not ui and not llm_chat_task.ui_factories:
                ui = StdUI()
            tool_confirmation = ToolCallHandler(
                tool_policies=llm_chat_task.tool_policies,
                argument_formatters=llm_chat_task.argument_formatters,
                response_handlers=llm_chat_task.response_handlers,
            )
        else:
            # Non-interactive without policies: Use UI for approval
            # Skip the StdUI fallback when ui_factories are present: the
            # non-interactive session resolves them and attaches the resulting
            # UI(s) (e.g. the web/SSE HTTPUI) so run_agent streams through those
            # instead of stdout.
            if not ui and not llm_chat_task.ui_factories:
                ui = StdUI()
            # tool_confirmation = None (let UI handle it via approval_channel)

        # Capability lookup for the resolved tool surface, used only when a
        # permission policy is in force (keyed by the LLM-visible tool name).
        cap_by_name = {
            (getattr(t, "name", None) or getattr(t, "__name__", "")): tool_capability(t)
            for t in resolved_tools
        }

        def _should_skip_approval(tool_def=None):
            # Approval precedence chain:
            #   perm_policy: allow→auto-approve, deny→auto-approve (gate blocks),
            #                ask→defer to tool_policy cascade
            #   tool_policy: handled in _resolve_approval (deferred_calls.py)
            #   yolo:        handled in _resolve_approval (deferred_calls.py)
            policy = get_effective_policy()
            if policy is not None:
                tool_name = (
                    getattr(tool_def, "name", str(tool_def))
                    if tool_def is not None
                    else ""
                )
                cap = cap_by_name.get(tool_name, Capability.UNKNOWN)
                result = policy.decide(tool_name, cap, {})
                if result is not None:
                    if result == ALLOW:
                        return True  # unconditional auto-approve
                    if result == DENY:
                        return True  # auto-approved (gate blocks at execution)
                    if result == ASK:
                        return False  # explicit policy ASK is a 'hard ask'
                # fallback to YOLO only if policy has no matching rule
            yolo_xcom_key = llm_chat_task.ui_config.yolo_xcom_key
            if yolo_xcom_key not in ctx.xcom:
                return False
            yolo_value = ctx.xcom[yolo_xcom_key].get(False)
            if isinstance(yolo_value, bool):
                return yolo_value
            if isinstance(yolo_value, frozenset):
                if tool_def is None:
                    return False
                tool_name = getattr(tool_def, "name", str(tool_def))
                return tool_name in yolo_value
            return False

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
        # Hold a reference so the interactive teardown can fire the terminal
        # SESSION_END on this exact manager (run_agent fires per-turn STOP, not
        # SESSION_END — SESSION_END is once-per-session, like Claude Code).
        llm_chat_task.active_hook_manager = hook_manager

        # Resolve sandbox against the outer (LLMChatTask) context before passing
        # to the inner LLMTask, whose own context does not carry a "sandbox" input
        # (see run_non_interactive_session / run_interactive_session).
        resolved_sandbox = coerce_sandbox(ctx, llm_chat_task.sandbox)

        # The inner task's conversation identity is always the active chat
        # session, never llm_chat_task's own conversation_name/render setting
        # — every field here is an explicit override, not a passthrough of
        # llm_chat_task.history_config. render_conversation_name=True is
        # pinned deliberately: the session template below only resolves
        # correctly when rendered, regardless of what llm_chat_task itself
        # was configured with.
        resolved_history = replace(
            llm_chat_task.history_config,
            history_manager=history_manager,
            conversation_name="{ctx.input.session}",
            render_conversation_name=True,
        )

        return _InnerTaskResolution(
            tool_confirmation=tool_confirmation,
            ui=cast("UIProtocol | None", ui),
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
        return resolve_conversation_name(
            ctx,
            self._llm_chat_task.conversation_name,
            self._llm_chat_task.render_conversation_name,
        )

    def get_ui_conversation_name(
        self, ui: "UIProtocol", initial_conversation_name: str
    ) -> str:
        """Get the current conversation name from UI or fallback to initial name."""
        if isinstance(ui, BaseUI):
            return ui.conversation_session_name
        return getattr(ui, "conversation_session_name", initial_conversation_name)

    def get_model(self, ctx: AnyContext) -> str | Model:
        """Resolve the model to use for this run.

        A templated model name is rendered against `ctx` when the task was
        built with `render_model`. An empty result falls back to the model from
        `llm_config`.
        """
        return resolve_model(
            ctx,
            self._llm_chat_task.model,
            self._llm_chat_task.render_model,
            self._llm_chat_task.llm_config,
        )
