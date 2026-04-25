from __future__ import annotations

import asyncio
import logging
import subprocess
from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.app.keybinding import create_output_keybindings
from zrb.llm.app.layout import create_input_field, create_layout, create_output_field
from zrb.llm.app.redirection import GlobalStreamCapture
from zrb.llm.app.style import create_style
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.llm_task import LLMTask
from zrb.llm.tool_call import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
)
from zrb.llm.ui.base.ui import BaseUI
from zrb.llm.ui.default.confirmation_mixin import ConfirmationMixin
from zrb.llm.ui.default.keybindings_mixin import KeybindingsMixin
from zrb.llm.ui.default.lifecycle_mixin import LifecycleMixin
from zrb.llm.ui.default.output_mixin import OutputMixin
from zrb.util.ascii_art.banner import create_banner
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

logger = logging.getLogger(__name__)


class UI(
    LifecycleMixin,
    KeybindingsMixin,
    ConfirmationMixin,
    OutputMixin,
    BaseUI,
):
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
        initial_attachments: list["UserContent"] = [],
        conversation_session_name: str = "",
        is_yolo: bool | frozenset = False,
        triggers: list[Callable[[], AsyncIterable[Any]]] = [],
        response_handlers: list[ResponseHandler] = [],
        tool_policies: list[ToolPolicy] = [],
        argument_formatters: list[ArgumentFormatter] = [],
        markdown_theme: "Theme | None" = None,
        summarize_commands: list[str] = [],
        attach_commands: list[str] = [],
        exit_commands: list[str] = [],
        info_commands: list[str] = [],
        save_commands: list[str] = [],
        load_commands: list[str] = [],
        rewind_commands: list[str] = [],
        redirect_output_commands: list[str] = [],
        yolo_toggle_commands: list[str] = [],
        set_model_commands: list[str] = [],
        exec_commands: list[str] = [],
        btw_commands: list[str] = [],
        custom_commands: list[AnyCustomCommand] = [],
        model: "Model | str | None" = None,
        custom_model_names: list[str] = [],
        show_ollama_models: bool = True,
        show_pydantic_ai_models: bool = True,
        enable_rewind: bool = False,
        snapshot_dir: str = "",
    ):
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
            custom_commands=custom_commands,
            model=model,
            enable_rewind=enable_rewind,
            snapshot_dir=snapshot_dir,
        )
        self._ascii_art = ascii_art
        self._jargon = jargon

        self._refresh_task: asyncio.Task | None = None

        self._capture = GlobalStreamCapture(self.append_to_output)
        self._style = create_style()

        from prompt_toolkit.history import InMemoryHistory

        self._input_history = InMemoryHistory()
        self._input_field = create_input_field(
            history_manager=self._history_manager,
            attach_commands=self._attach_commands,
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
            custom_commands=self._custom_commands,
            history=self._input_history,
            custom_model_names=custom_model_names,
            show_ollama_models=show_ollama_models,
            show_pydantic_ai_models=show_pydantic_ai_models,
        )

        help_text = self._get_help_text(limit=25)
        full_greeting = create_banner(self._ascii_art, f"{greeting}\n{help_text}")
        custom_output_kb = create_output_keybindings(self._input_field)
        self._output_field = create_output_field(
            full_greeting, output_lexer, key_bindings=custom_output_kb
        )

        self._layout = create_layout(
            title=self._assistant_name,
            jargon=self._jargon,
            input_field=self._input_field,
            output_field=self._output_field,
            info_bar_text=self._get_info_bar_text,
            status_bar_text=self._get_status_bar_text,
        )

        from prompt_toolkit.key_binding import KeyBindings

        self._app_kb = KeyBindings()
        self._setup_app_keybindings(
            app_keybindings=self._app_kb, llm_task=self._llm_task
        )
        self._application = self._create_application(
            layout=self._layout, keybindings=self._app_kb, style=self._style
        )

        if self._initial_message:
            self._application.after_render.add_handler(self._on_first_render)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
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

    def _create_application(
        self,
        layout: "Layout",
        keybindings: "KeyBindings",
        style: "Style",
    ) -> "Application":
        from prompt_toolkit import Application
        from prompt_toolkit.output import create_output

        try:
            from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard

            clipboard = PyperclipClipboard()
        except ImportError:
            from prompt_toolkit.clipboard import InMemoryClipboard

            clipboard = InMemoryClipboard()
        except Exception:
            from prompt_toolkit.clipboard import InMemoryClipboard

            clipboard = InMemoryClipboard()

        output = create_output(stdout=self._capture.get_original_stdout())

        # Wrap output.get_size to survive a console-not-detected error on Windows.
        original_get_size = output.get_size

        def robust_get_size():
            try:
                return original_get_size()
            except Exception:
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
