from typing import Callable

from prompt_toolkit.formatted_text import HTML, AnyFormattedText
from prompt_toolkit.layout import HSplit, Layout, Window, WindowAlign
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import Frame, TextArea

from zrb.llm.app.completion import InputCompleter
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


def create_input_field(
    history_manager: AnyHistoryManager,
    attach_commands: list[str],
    exit_commands: list[str],
    info_commands: list[str],
    save_commands: list[str],
    load_commands: list[str],
    redirect_output_commands: list[str],
    summarize_commands: list[str],
    exec_commands: list[str],
    custom_commands: list[AnyCustomCommand],
) -> TextArea:
    return TextArea(
        height=4,
        prompt=HTML('<style color="ansibrightblue"><b>&gt;&gt;&gt; </b></style>'),
        multiline=True,
        wrap_lines=True,
        completer=InputCompleter(
            history_manager=history_manager,
            attach_commands=attach_commands,
            exit_commands=exit_commands,
            info_commands=info_commands,
            save_commands=save_commands,
            load_commands=load_commands,
            redirect_output_commands=redirect_output_commands,
            summarize_commands=summarize_commands,
            exec_commands=exec_commands,
            custom_commands=custom_commands,
        ),
        complete_while_typing=True,
        focus_on_click=True,
        style="class:input_field",
    )


def create_output_field(greeting: str, lexer: Lexer) -> TextArea:
    return TextArea(
        text=greeting.rstrip() + "\n\n",
        read_only=True,
        scrollbar=False,
        wrap_lines=True,
        lexer=lexer,
        focus_on_click=True,
        focusable=True,
        style="class:output_field",
    )


def create_layout(
    title: str,
    jargon: str,
    input_field: TextArea,
    output_field: TextArea,
    info_bar_text: Callable[[], AnyFormattedText],
    status_bar_text: Callable[[], AnyFormattedText],
) -> Layout:
    title_bar_text = HTML(
        f" <style bg='ansipurple' color='white'><b> {title} </b></style> "
        f"<style color='#888888'>| {jargon}</style>"
    )

    return Layout(
        FloatContainer(
            content=HSplit(
                [
                    # Title Bar
                    Window(
                        height=2,
                        content=FormattedTextControl(title_bar_text),
                        style="class:title-bar",
                        align=WindowAlign.CENTER,
                    ),
                    # Info Bar
                    Window(
                        height=3,
                        content=FormattedTextControl(info_bar_text),
                        style="class:info-bar",
                        align=WindowAlign.CENTER,
                    ),
                    # Chat History
                    Frame(output_field, title="Conversation", style="class:frame"),
                    # Input Area
                    Frame(
                        input_field,
                        title="(ENTER to send, CTRL+ENTER for newline, ESC to cancel)",
                        style="class:input-frame",
                    ),
                    # Status Bar
                    Window(
                        height=1,
                        content=FormattedTextControl(status_bar_text),
                        style="class:bottom-toolbar",
                    ),
                ]
            ),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=16, scroll_offset=1),
                ),
            ],
        ),
        focused_element=input_field,
    )
