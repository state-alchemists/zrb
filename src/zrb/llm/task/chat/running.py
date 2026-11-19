"""`LLMChatTask` session runners: drive a built inner `LLMTask` either as a
one-shot run or through an interactive UI.

The interactive half is presentation work — it assembles a UI, runs its loop
and reads its display — and lives in `zrb.llm.ui.session`. `ChatRunning` asks
`shared/session_presentation.py` for it and keeps the one-shot half here, which
needs no UI beyond the ones already attached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.context.shared_context import SharedContext
from zrb.llm.custom_command.resolver import resolve_custom_commands
from zrb.llm.contracts.shared.feature_config import bound_session_ui
from zrb.llm.contracts.shared.session_presentation import get_interactive_runner
from zrb.llm.task.chat.message_expansion import expand_message
from zrb.llm.contracts.util.spoken import shown_text
from zrb.session.session import Session

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeAlias, TypedDict

    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import UserContent
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.capabilities.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.task.chat.task import LLMChatTask
    from zrb.llm.task.llm_task import LLMTask
    from zrb.llm.ui.any_ui import AnyUI

    #: Builds the UI(s) a session runs through, from the session's own values.
    #: The interactive path also passes `custom_commands`, a ninth keyword
    #: (`docs/llm/llm-custom-ui.md`, create_ui_factory), which a `Callable`
    #: spec cannot state as optional: a factory used in an interactive session
    #: must accept it.
    UIFactory: TypeAlias = Callable[
        [
            AnyContext,
            LLMTask,
            AnyHistoryManager,
            dict[str, list[str]],
            str | None,
            str,
            bool,
            list[UserContent],
        ],
        "AnyUI | list[AnyUI]",
    ]

    class SessionRunArgs(TypedDict):
        """What a session runner needs, named once.

        The facade's two delegators take these as keywords, so the names live
        here beside the implementation instead of being repeated there.
        """

        ctx: AnyContext
        llm_task_core: LLMTask
        history_manager: AnyHistoryManager
        ui_commands: dict[str, list[str]]
        initial_message: str | None
        initial_conversation_name: str
        initial_yolo: bool | frozenset[str]
        initial_attachments: list[UserContent]

    class InteractiveSessionRunArgs(SessionRunArgs, total=False):
        """`SessionRunArgs` plus the two knobs only the interactive loop has."""

        enable_rewind: bool
        snapshot_dir: str


class ChatRunning:
    """The one-shot session for LLMChatTask, and the interactive one's way in.

    A one-shot run needs no UI it was not given, so it lives here. An
    interactive run builds one, and that half is asked for from the
    presentation layer — see `run_interactive_session`.
    """

    def __init__(self, llm_chat_task: "LLMChatTask") -> None:
        self._llm_chat_task = llm_chat_task

    @property
    def llm_chat_task(self) -> "LLMChatTask":
        """The owning `LLMChatTask` this runner reads state from."""
        return self._llm_chat_task

    async def run_non_interactive_session(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        ui_commands: dict[str, list[str]],
        initial_message: str | None,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
    ) -> object:
        effective_message, reply = expand_message(
            initial_message, self._resolve_custom_commands()
        )
        if effective_message is None:
            # An action command ran in place of the turn.
            if reply:
                ctx.print(reply, plain=True)
            return reply

        # Factory-produced UIs (e.g. the web/SSE HTTPUI) become output sinks so
        # run_agent streams through them. Programmatic `uis` are already wired
        # in by `_create_llm_task_core`; factories need the core task instance.
        self._attach_ui_factories(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=effective_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
        )

        session_input = {
            "message": effective_message,
            "session": initial_conversation_name,
            "yolo": bool(initial_yolo),  # inner task uses dynamic_yolo; just pass bool
            "attachments": initial_attachments,
            "model": self._llm_chat_task.get_model(ctx),
            "interactive": False,
        }
        shared_ctx = SharedContext(
            input=session_input,
            print_fn=ctx.shared_print,
        )
        session = Session(shared_ctx)
        uis = llm_task_core.get_uis()
        # the first sink stands for the session; the web runner
        # attaches one HTTPUI, so there is no second to choose from.
        with bound_session_ui(uis[0] if uis else None):
            result = await llm_task_core.async_run(session)
        # Unlike stream_ai_response, this path never finalizes with a rendered
        # pass, so do it here for every UI that supports it. The answer keeps
        # its `<spoken>` markers for speech; a screen shows it without them.
        if isinstance(result, str):
            shown = shown_text(result)
            for ui in llm_task_core.get_uis():
                _append_shown_answer(ui, shown)
        ctx.xcom["__conversation_name__"] = initial_conversation_name
        return result

    def _attach_ui_factories(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        ui_commands: dict[str, list[str]],
        initial_message: str | None,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
    ) -> None:
        """Resolve the UI factories and attach the results to the core task."""
        for factory in self._llm_chat_task.ui_factories:
            factory_ui = factory(
                ctx=ctx,
                llm_task=llm_task_core,
                history_manager=history_manager,
                ui_commands=ui_commands,
                initial_message=initial_message,
                initial_conversation_name=initial_conversation_name,
                initial_yolo=initial_yolo,
                initial_attachments=initial_attachments,
            )
            for ui in factory_ui if isinstance(factory_ui, list) else [factory_ui]:
                llm_task_core.append_ui(ui)

    def _resolve_custom_commands(self) -> list["AnyCustomCommand"]:
        """Resolve custom commands, calling any callable factories."""
        return resolve_custom_commands(self._llm_chat_task.custom_commands)

    async def run_interactive_session(
        self,
        ctx: "AnyContext",
        llm_task_core: "LLMTask",
        history_manager: "AnyHistoryManager",
        ui_commands: dict[str, list[str]],
        initial_message: str | None,
        initial_conversation_name: str,
        initial_yolo: "bool | frozenset[str]",
        initial_attachments: "list[UserContent]",
        enable_rewind: bool = False,
        snapshot_dir: str = "",
    ) -> object:
        """Run the session through the UI the presentation layer assembles.

        Assembling that UI, and running its loop, is presentation work and
        lives in `zrb.llm.ui.session`; the command offering an interactive
        chat registers it there (`builtin/llm/chat.py`). A task asked to run
        interactively with nothing registered has no way to present itself, so
        it says that instead of running without the session loop.
        """
        runner = get_interactive_runner()
        if runner is None:
            raise RuntimeError(
                "No interactive session runner is registered. An interactive "
                "chat presents itself through `zrb llm chat`, which registers "
                "one; a task run another way can only run one-shot "
                "(run_non_interactive_session)."
            )
        return await runner(
            self._llm_chat_task,
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=initial_message,
            initial_conversation_name=initial_conversation_name,
            initial_yolo=initial_yolo,
            initial_attachments=initial_attachments,
            enable_rewind=enable_rewind,
            snapshot_dir=snapshot_dir,
        )


def _append_shown_answer(ui: "AnyUI", shown: str) -> None:
    """Put a finished turn's answer on *ui* through `append_answer`.

    `append_answer` is where a UI that lays a run's output out in a column puts
    the answer, so it lands where the streamed copy was; a UI that does not
    override it gets the text through `append_markdown`. Skipping it here
    would draw a non-interactive answer at the margin while the same answer in
    an interactive session sits in the column.
    """
    ui.display.append_answer(shown)
