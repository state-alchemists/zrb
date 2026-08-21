from __future__ import annotations

import asyncio
import logging
import subprocess
from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.tool_call import ArgumentFormatter, ResponseHandler, ToolPolicy
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.default.agent_picker import UIAgentPicker
from zrb.llm.ui.default.app.keybinding import create_output_keybindings
from zrb.llm.ui.default.app.layout import (
    create_input_field,
    create_layout,
    create_output_field,
)
from zrb.llm.ui.default.app.redirection import GlobalStreamCapture
from zrb.llm.ui.default.app.style import create_style
from zrb.llm.ui.default.confirmation import UIConfirmation
from zrb.llm.ui.default.keybindings import UIKeybindings
from zrb.llm.ui.default.lifecycle import UILifecycle
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput
from zrb.llm.ui.default.selection import UISelection
from zrb.util.ascii_art.banner import get_ascii_art
from zrb.util.cli.help_panel import render_help_panel
from zrb.util.cli.terminal import get_terminal_size

if TYPE_CHECKING:
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.styles import Style
    from pydantic_ai import UserContent
    from pydantic_ai.models import Model
    from rich.theme import Theme

    from zrb.llm.task.llm_task import LLMTask

logger = logging.getLogger(__name__)

# The greeting shares the screen with the conversation, so it lists at most
# this many commands and points at `/help` for the rest.
GREETING_COMMAND_LIMIT = 20


class UI(BaseUI):
    def __init__(
        self,
        ctx: AnyContext,
        yolo_xcom_key: str,
        greeting: str,
        assistant_name: str,
        ascii_art: str,
        jargon: str,
        output_lexer: Lexer,
        llm_task: LLMTask,
        history_manager: AnyHistoryManager,
        initial_message: Any = "",
        initial_attachments: "list[UserContent] | None" = None,
        conversation_session_name: str = "",
        is_yolo: bool | frozenset = False,
        triggers: list[Callable[[], AsyncIterable[Any]]] | None = None,
        response_handlers: list[ResponseHandler] | None = None,
        tool_policies: list[ToolPolicy] | None = None,
        argument_formatters: list[ArgumentFormatter] | None = None,
        markdown_theme: "Theme | None" = None,
        summarize_commands: list[str] | None = None,
        attach_commands: list[str] | None = None,
        photo_commands: list[str] | None = None,
        exit_commands: list[str] | None = None,
        info_commands: list[str] | None = None,
        save_commands: list[str] | None = None,
        load_commands: list[str] | None = None,
        rewind_commands: list[str] | None = None,
        redirect_output_commands: list[str] | None = None,
        yolo_toggle_commands: list[str] | None = None,
        set_model_commands: list[str] | None = None,
        exec_commands: list[str] | None = None,
        btw_commands: list[str] | None = None,
        plan_commands: list[str] | None = None,
        copy_commands: list[str] | None = None,
        voice_commands: list[str] | None = None,
        custom_commands: list[AnyCustomCommand] | None = None,
        model: "Model | str | None" = None,
        custom_model_names: list[str] | None = None,
        show_ollama_models: bool = True,
        show_pydantic_ai_models: bool = True,
        enable_rewind: bool = False,
        snapshot_dir: str = "",
    ):
        self._pending_invalidate = False
        self._invalidate_task: asyncio.Task | None = None
        # [start, end, source, renderer] per width-dependent block appended
        # through `append_rendered` — see that method and `rewrap_output`.
        self._rendered_blocks: list[list] = []
        self._rendered_width: int | None = None
        super().__init__(
            ctx=ctx,
            yolo_xcom_key=yolo_xcom_key,
            assistant_name=assistant_name,
            llm_task=llm_task,
            history_manager=history_manager,
            initial_message=initial_message,
            initial_attachments=initial_attachments,
            conversation_session_name=conversation_session_name,
            is_yolo=is_yolo,
            triggers=triggers,
            response_handlers=response_handlers,
            tool_policies=tool_policies,
            argument_formatters=argument_formatters,
            markdown_theme=markdown_theme,
            summarize_commands=summarize_commands,
            attach_commands=attach_commands,
            photo_commands=photo_commands,
            exit_commands=exit_commands,
            info_commands=info_commands,
            save_commands=save_commands,
            load_commands=load_commands,
            rewind_commands=rewind_commands,
            redirect_output_commands=redirect_output_commands,
            yolo_toggle_commands=yolo_toggle_commands,
            set_model_commands=set_model_commands,
            exec_commands=exec_commands,
            btw_commands=btw_commands,
            plan_commands=plan_commands,
            copy_commands=copy_commands,
            voice_commands=voice_commands,
            custom_commands=custom_commands,
            model=model,
            enable_rewind=enable_rewind,
            snapshot_dir=snapshot_dir,
        )
        self._lifecycle = UILifecycle(self)
        self._output = UIOutput(self)
        self._confirmation = UIConfirmation(self)
        self._selection = UISelection(self, confirmation=self._confirmation)
        self._message_editing = UIMessageEditing(self)
        self._agent_picker = UIAgentPicker(self)
        self._keybindings = UIKeybindings(self)

        self._ascii_art = ascii_art
        self._jargon = jargon

        self._refresh_task: asyncio.Task | None = None

        self._capture = GlobalStreamCapture()
        self._style = create_style()

        # lazy: heavy third-party
        from prompt_toolkit.history import InMemoryHistory

        self._input_history = InMemoryHistory()
        self._input_field = create_input_field(
            history_manager=self._history_manager,
            attach_commands=self._attach_commands,
            photo_commands=self._photo_commands,
            exit_commands=self._exit_commands,
            info_commands=self._info_commands,
            save_commands=self._save_commands,
            load_commands=self._load_commands,
            rewind_commands=(
                self._rewind_commands if self._snapshot_manager is not None else []
            ),
            redirect_output_commands=self._redirect_output_commands,
            summarize_commands=self._summarize_commands,
            set_model_commands=self._set_model_commands,
            exec_commands=self._exec_commands,
            btw_commands=self._btw_commands,
            plan_commands=self._plan_commands,
            copy_commands=self._copy_commands,
            voice_commands=self._voice_commands,
            custom_commands=self._custom_commands,
            history=self._input_history,
            custom_model_names=custom_model_names,
            show_ollama_models=show_ollama_models,
            show_pydantic_ai_models=show_pydantic_ai_models,
            up_arrow_handler=self.handle_up_arrow,
            down_arrow_handler=self.handle_down_arrow,
            recall_active=self.recall_navigation_active,
        )

        custom_output_kb = create_output_keybindings(self._input_field)
        self._output_field = create_output_field(
            "", output_lexer, key_bindings=custom_output_kb
        )
        # Resolved once: an unknown art name falls back to a *random* file, so
        # re-resolving per render would reshuffle the image on every resize.
        greeting_panel = self.get_help_panel(
            art=get_ascii_art(self._ascii_art),
            header=greeting,
            max_commands=GREETING_COMMAND_LIMIT,
        )
        self.append_rendered(greeting_panel, render_help_panel)
        self.append_to_output("")

        # AskUserQuestion selection widget (hidden until a choice is active).
        self._selection.init_selection_state()
        choice_float = self._create_choice_float()

        # Sub-agent picker + live view (hidden until Down Arrow opens it).
        self._agent_picker.init_agent_picker_state()
        agent_picker_float = self._create_agent_picker_float()

        self._layout = create_layout(
            title=self._assistant_name,
            jargon=self._jargon,
            input_field=self._input_field,
            output_field=self._output_field,
            info_bar_text=self.get_info_bar_text,
            status_bar_text=self.get_status_bar_text,
            extra_floats=[choice_float, agent_picker_float],
            agent_activity_text=self.get_agent_activity_text,
        )

        # lazy: heavy third-party
        from prompt_toolkit.key_binding import KeyBindings

        self._app_kb = KeyBindings()
        self.setup_app_keybindings(
            app_keybindings=self._app_kb, llm_task=self._llm_task
        )
        self._application = self._create_application(
            layout=self._layout, keybindings=self._app_kb, style=self._style
        )

        # prompt_toolkit redraws on SIGWINCH, so a render is the cheapest place
        # to notice a new width and re-wrap the markdown already on screen.
        self._application.after_render.add_handler(self._on_render)

        if self._initial_message:
            self._application.after_render.add_handler(self.on_first_render)

    def _on_render(self, app: "Application") -> None:
        try:
            if self.viewing_agent_id is not None:
                # While viewing a sub-agent the pane shows that agent's buffer
                # (see UIAgentPicker); the main transcript's re-wrap is parked
                # until Esc returns to it.
                self.sync_output_to_viewed_agent()
            else:
                self.rewrap_output()
        except Exception as e:
            # Runs on every frame — a re-render failure must not kill the paint.
            # Log only the first occurrence of each distinct failure: the same
            # failure on every frame would otherwise print a warning per
            # redraw (a "recurring error" wall of identical lines).
            message = f"Output re-wrap skipped: {e}"
            if message != getattr(self, "_last_render_error", None):
                self._last_render_error = message
                logger.warning(message)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        # lazy: heavy third-party
        from prompt_toolkit.application import run_in_terminal

        def run_subprocess():
            # Standard streams inherit from the parent, which has been restored
            # to the TTY by self._capture.pause()
            subprocess.call(cmd, shell=shell)

        with self._capture.pause():
            await run_in_terminal(run_subprocess)

    @property
    def application(self) -> "Application":
        return self._application

    @property
    def capture(self) -> GlobalStreamCapture:
        """The stdout/stderr capture guarding the terminal while the app runs."""
        return self._capture

    @property
    def refresh_task(self) -> "asyncio.Task | None":
        """The task running the periodic repaint loop, if started."""
        return self._refresh_task

    @refresh_task.setter
    def refresh_task(self, value: "asyncio.Task | None") -> None:
        self._refresh_task = value

    @property
    def rendered_blocks(self) -> "list[list]":
        """[start, end, source, renderer] per width-dependent rendered block."""
        return self._rendered_blocks

    @property
    def rendered_width(self) -> "int | None":
        """The output width the tracked rendered blocks were last wrapped at."""
        return self._rendered_width

    @rendered_width.setter
    def rendered_width(self, value: "int | None") -> None:
        self._rendered_width = value

    @property
    def pending_invalidate(self) -> bool:
        """Whether a debounced repaint is already scheduled."""
        return self._pending_invalidate

    @pending_invalidate.setter
    def pending_invalidate(self, value: bool) -> None:
        self._pending_invalidate = value

    @property
    def invalidate_task(self) -> "asyncio.Task | None":
        """The task running the debounced repaint, if scheduled."""
        return self._invalidate_task

    @invalidate_task.setter
    def invalidate_task(self, value: "asyncio.Task | None") -> None:
        self._invalidate_task = value

    def _create_choice_float(self):
        """Float hosting the AskUserQuestion widget, shown only when active."""
        # lazy: heavy third-party
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.layout.containers import ConditionalContainer, Float
        from prompt_toolkit.widgets import Frame

        framed = Frame(
            self._selection._choice_window,
            title="Select an answer",
            style="class:choice-frame",
        )
        # Full-width (left=right=0): a narrower float leaves side margins where the
        # streaming output behind it bleeds through. Anchored just above the input.
        return Float(
            bottom=4,
            left=0,
            right=0,
            content=ConditionalContainer(
                content=framed, filter=Condition(self.has_active_choice)
            ),
        )

    def _create_agent_picker_float(self):
        """Float hosting the sub-agent picker, shown only while active."""
        # lazy: heavy third-party
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.layout.containers import ConditionalContainer, Float
        from prompt_toolkit.widgets import Frame

        framed = Frame(
            self._agent_picker.agent_picker_window,
            title="Talk to a sub-agent",
            style="class:agent-picker-frame",
        )
        # Full-width (left=right=0), anchored just above the input, matching
        # the choice float.
        return Float(
            bottom=4,
            left=0,
            right=0,
            content=ConditionalContainer(
                content=framed, filter=Condition(self.has_active_agent_picker)
            ),
        )

    def _create_application(
        self,
        layout: "Layout",
        keybindings: "KeyBindings",
        style: "Style",
    ) -> "Application":
        # lazy: heavy third-party
        from prompt_toolkit import Application
        from prompt_toolkit.output import create_output

        try:
            # lazy: heavy third-party
            from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard

            clipboard = PyperclipClipboard()
        except ImportError:
            # lazy: heavy third-party
            from prompt_toolkit.clipboard import InMemoryClipboard

            clipboard = InMemoryClipboard()
        except Exception:
            # lazy: heavy third-party
            from prompt_toolkit.clipboard import InMemoryClipboard

            clipboard = InMemoryClipboard()

        output = create_output(stdout=self._capture.get_original_stdout())

        # Wrap output.get_size to survive a console-not-detected error on Windows.
        original_get_size = output.get_size

        def robust_get_size():
            try:
                return original_get_size()
            except Exception:
                # lazy: heavy third-party
                from prompt_toolkit.data_structures import Size

                size = get_terminal_size()
                return Size(rows=size.lines, columns=size.columns)

        output.get_size = robust_get_size

        return Application(
            layout=layout,
            key_bindings=keybindings,
            style=style,
            full_screen=True,
            mouse_support=True,
            refresh_interval=CFG.LLM_UI_REFRESH_INTERVAL / 1000,
            output=output,
            clipboard=clipboard,
        )

    # =========================================================================
    # UILifecycle delegators
    # =========================================================================

    async def cleanup_background_tasks(self) -> None:
        await self._lifecycle.cleanup_background_tasks()

    def handle_application_run_error(self, exc: Exception) -> None:
        self._lifecycle.handle_application_run_error(exc)

    async def run_async(self) -> Any:
        return await self._lifecycle.run_async()

    def handle_first_render(self) -> None:
        self._lifecycle.handle_first_render()

    def on_first_render(self, app: "Application") -> None:
        self._lifecycle.on_first_render(app)

    def invalidate_ui(self) -> None:
        self._lifecycle.invalidate_ui()

    def on_exit(self) -> None:
        self._lifecycle.on_exit()

    # =========================================================================
    # UIAgentPicker delegators
    # =========================================================================

    def has_active_agent_picker(self) -> bool:
        return self._agent_picker.has_active_agent_picker()

    @property
    def viewing_agent_id(self) -> str | None:
        return self._agent_picker.viewing_agent_id

    @property
    def saved_main_output(self) -> str | None:
        return self._agent_picker.saved_main_output

    @saved_main_output.setter
    def saved_main_output(self, value: str | None) -> None:
        self._agent_picker.saved_main_output = value

    def open_agent_picker(self) -> bool:
        return self._agent_picker.open_agent_picker()

    def close_agent_picker(self) -> None:
        self._agent_picker.close_agent_picker()

    def move_agent_picker_cursor(self, delta: int) -> None:
        self._agent_picker.move_agent_picker_cursor(delta)

    def confirm_agent_picker(self) -> bool:
        return self._agent_picker.confirm_agent_picker()

    def enter_agent_view(self, session: Any) -> None:
        self._agent_picker.enter_agent_view(session)

    def exit_agent_view(self) -> None:
        self._agent_picker.exit_agent_view()

    def cancel_viewed_agent(self) -> bool:
        return self._agent_picker.cancel_viewed_agent()

    def sync_output_to_viewed_agent(self) -> None:
        self._agent_picker.sync_output_to_viewed_agent()

    # =========================================================================
    # UIMessageEditing delegators
    # =========================================================================

    @property
    def queued_edit_entry(self) -> Any:
        return self._message_editing.queued_edit_entry

    def handle_up_arrow(self, event: Any) -> bool:
        return self._message_editing.handle_up_arrow(event)

    def handle_down_arrow(self, event: Any) -> bool:
        return self._message_editing.handle_down_arrow(event)

    def recall_navigation_active(self) -> bool:
        return self._message_editing.recall_navigation_active()

    def handle_enter_queued_edit(self, event: Any) -> bool:
        return self._message_editing.handle_enter_queued_edit(event)

    def _track_echo_span(self, entry: Any, echo: str) -> None:
        """Override hook `BaseUI` invokes polymorphically (see its base no-op)."""
        self._message_editing.track_echo_span(entry, echo)

    def _redraw_echo(self, entry: Any) -> None:
        """Override hook `BaseUI` invokes polymorphically (see its base no-op)."""
        self._message_editing.redraw_echo(entry)

    # =========================================================================
    # UIOutput delegators
    # =========================================================================
    # `is_thinking`/`current_confirmation` are not redeclared here: `UI` is a
    # genuine `BaseUI` subclass (is-a, not composed), and `BaseUI` already
    # owns that state and exposes it correctly — inheriting it is enough.

    @property
    def output_part(self) -> "UIOutput":
        """The composed `UIOutput` part (public seam for tests)."""
        return self._output

    @property
    def output_text(self) -> str:
        return self._output.output_text

    @property
    def output_field(self) -> Any:
        """The prompt-toolkit output-field widget (own field, TUI-specific)."""
        return self._output_field

    @property
    def input_field(self) -> Any:
        """The prompt-toolkit input-field widget (own field, TUI-specific)."""
        return self._input_field

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: Any = None,
        flush: bool = False,
        kind: str = "text",
    ) -> None:
        self._output.append_to_output(
            *values, sep=sep, end=end, file=file, flush=flush, kind=kind
        )

    def append_markdown(self, markdown_text: str) -> None:
        self._output.append_markdown(markdown_text)

    def print_help(self) -> None:
        self._output.print_help()

    def append_rendered(
        self, source: Any, renderer: "Callable[[Any, int | None], str]"
    ) -> None:
        self._output.append_rendered(source, renderer)

    def rewrap_output(self) -> None:
        self._output.rewrap_output()

    def replace_output_span(self, start: int, end: int, replacement: str) -> bool:
        return self._output.replace_output_span(start, end, replacement)

    def set_output_text(self, text: str) -> None:
        self._output.set_output_text(text)

    @property
    def output_field_width(self) -> int | None:
        return self._output.output_field_width

    def get_info_bar_text(self) -> Any:
        return self._output.get_info_bar_text()

    def get_agent_activity_text(self) -> Any:
        return self._output.get_agent_activity_text()

    def get_status_bar_text(self) -> Any:
        return self._output.get_status_bar_text()

    def schedule_invalidate(self) -> None:
        self._output.schedule_invalidate()

    # =========================================================================
    # UIConfirmation delegators
    # =========================================================================

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        return await self._confirmation.ask_user(prompt, output_to_parent, agent_id)

    async def ask_user_choice(self, spec: Any, agent_id: str | None = None) -> str:
        return await self._confirmation.ask_user_choice(spec, agent_id)

    def submit_user_answer(self, text: str) -> bool:
        return self._confirmation.submit_user_answer(text)

    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        self._confirmation.cancel_pending_confirmations(flush=flush)

    def resolve_current(self, text: str, echo: str | None) -> bool:
        return self._confirmation.resolve_current(text, echo)

    def begin_choice(self, spec: Any) -> None:
        self._selection.begin_choice(spec)

    def end_choice(self) -> None:
        self._selection.end_choice()

    def handle_confirmation(self, event: Any) -> bool:
        # `UISelection` is the front: it handles the pending-free-text case
        # and falls through to `UIConfirmation`'s base case otherwise —
        # mirroring the old MRO where `UISelection` preceded `UIConfirmation`.
        return self._selection.handle_confirmation(event)

    # =========================================================================
    # UISelection delegators
    # =========================================================================

    def has_active_choice(self) -> bool:
        return self._selection.has_active_choice()

    def move_choice_cursor(self, delta: int) -> None:
        self._selection.move_choice_cursor(delta)

    def toggle_choice_current(self) -> None:
        self._selection.toggle_choice_current()

    def confirm_choice(self) -> bool:
        return self._selection.confirm_choice()

    # =========================================================================
    # UIKeybindings delegators
    # =========================================================================

    def setup_app_keybindings(
        self, app_keybindings: "KeyBindings", llm_task: Any
    ) -> None:
        self._keybindings.setup_app_keybindings(app_keybindings, llm_task)
