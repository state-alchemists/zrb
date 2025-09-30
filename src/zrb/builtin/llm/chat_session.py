"""
This module provides functions for managing interactive chat sessions with an LLM.

It handles reading user input, triggering the LLM task, and managing the
conversation flow via XCom.
"""

import asyncio
import sys
from typing import TYPE_CHECKING, Any

from zrb.builtin.llm.chat_trigger import llm_chat_trigger
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import stylize_blue, stylize_bold_yellow, stylize_faint
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from asyncio import StreamReader

    from prompt_toolkit import PromptSession


async def read_user_prompt(ctx: AnyContext) -> str:
    """
    Reads user input from the CLI for an interactive chat session.
    Orchestrates the session by calling helper functions.
    """
    _show_info(ctx)
    is_tty: bool = ctx.is_tty
    reader: PromptSession[Any] | StreamReader = await _setup_input_reader(is_tty)
    multiline_mode = False
    is_first_time = True
    current_modes: str = ctx.input.modes
    current_yolo_mode: bool | str = ctx.input.yolo
    user_inputs: list[str] = []
    final_result: str = ""
    while True:
        await asyncio.sleep(0.01)
        previous_session_name: str | None = (
            ctx.input.previous_session if is_first_time else ""
        )
        start_new: bool = ctx.input.start_new if is_first_time else False
        if is_first_time and ctx.input.message.strip() != "":
            user_input = ctx.input.message
        else:
            # Get user input based on mode
            if not multiline_mode:
                ctx.print("💬 >>", plain=True)
            user_input = await llm_chat_trigger.wait(reader, ctx)
            if not multiline_mode:
                ctx.print("", plain=True)
        is_first_time = False
        # Handle user input
        if user_input.strip().lower() in ("/bye", "/quit", "/q", "/exit"):
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(
                ctx=ctx,
                user_prompt=user_prompt,
                modes=current_modes,
                yolo_mode=current_yolo_mode,
                previous_session_name=previous_session_name,
                start_new=start_new,
            )
            if result is not None:
                final_result = result
            break
        elif user_input.strip().lower() in ("/multi",):
            multiline_mode = True
        elif user_input.strip().lower() in ("/end",):
            ctx.print("", plain=True)
            multiline_mode = False
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(
                ctx=ctx,
                user_prompt=user_prompt,
                modes=current_modes,
                yolo_mode=current_yolo_mode,
                previous_session_name=previous_session_name,
                start_new=start_new,
            )
            if result is not None:
                final_result = result
                if ctx.is_web_mode or not is_tty:
                    return final_result
        elif user_input.strip().lower().startswith("/mode"):
            mode_parts = user_input.split(" ", maxsplit=2)
            if len(mode_parts) > 1:
                current_modes = mode_parts[1]
            ctx.print(f"Current mode: {current_modes}", plain=True)
            ctx.print("", plain=True)
            continue
        elif user_input.strip().lower().startswith("/yolo"):
            yolo_mode_parts = user_input.split(" ", maxsplit=2)
            if len(yolo_mode_parts) > 1:
                current_yolo_mode = to_boolean(yolo_mode_parts[1])
            ctx.print(f"Current_yolo mode: {current_yolo_mode}", plain=True)
            ctx.print("", plain=True)
            continue
        elif user_input.strip().lower() in ("/help", "/info"):
            _show_info(ctx)
            continue
        else:
            user_inputs.append(user_input)
            if multiline_mode:
                continue
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(
                ctx=ctx,
                user_prompt=user_prompt,
                modes=current_modes,
                yolo_mode=current_yolo_mode,
                previous_session_name=previous_session_name,
                start_new=start_new,
            )
            if result is not None:
                final_result = result
                if ctx.is_web_mode or not is_tty:
                    return final_result
    return final_result


def _show_info(ctx: AnyContext):
    """
    Displays the available chat session commands to the user.
    Args:
        ctx: The context object for the task.
    """
    ctx.print(
        "\n".join(
            [
                _show_command("/bye", "Quit from chat session"),
                _show_command("/multi", "Start multiline input"),
                _show_command("/end", "End multiline input"),
                _show_command("/modes", "Show current modes"),
                _show_subcommand("<mode1,mode2,..>", "Set current modes"),
                _show_command("/yolo", "Get current YOLO mode"),
                _show_subcommand("<true|false|list-of-tools>", "Set YOLO mode"),
                _show_command("/help", "Show this message"),
            ]
        ),
        plain=True,
    )
    ctx.print("", plain=True)


def _show_command(command: str, description: str) -> str:
    styled_command = stylize_bold_yellow(command.ljust(25))
    styled_description = stylize_faint(description)
    return f"  {styled_command} {styled_description}"


def _show_subcommand(command: str, description: str) -> str:
    styled_command = stylize_blue(f"    {command}".ljust(25))
    styled_description = stylize_faint(description)
    return f"  {styled_command} {styled_description}"


async def _setup_input_reader(
    is_interactive: bool,
) -> "PromptSession[Any] | StreamReader":
    """Sets up and returns the appropriate asynchronous input reader."""
    if is_interactive:
        from prompt_toolkit import PromptSession

        return PromptSession()

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return reader


async def _trigger_ask_and_wait_for_result(
    ctx: AnyContext,
    user_prompt: str,
    modes: str,
    yolo_mode: bool | str,
    previous_session_name: str | None = None,
    start_new: bool = False,
) -> str | None:
    """
    Triggers the LLM ask task and waits for the result via XCom.

    Args:
        ctx: The context object for the task.
        user_prompt: The user's message to send to the LLM.
        previous_session_name: The name of the previous chat session (optional).
        start_new: Whether to start a new conversation (optional).

    Returns:
        The result from the LLM task, or None if the user prompt is empty.
    """
    if user_prompt.strip() == "":
        return None
    await _trigger_ask(
        ctx, user_prompt, modes, yolo_mode, previous_session_name, start_new
    )
    result = await _wait_ask_result(ctx)
    md_result = render_markdown(result) if result is not None else ""
    ctx.print("\n🤖 >>", plain=True)
    ctx.print(md_result, plain=True)
    ctx.print("", plain=True)
    return result


def get_llm_ask_input_mapping(callback_ctx: AnyContext):
    """
    Generates the input mapping for the LLM ask task from the callback context.

    Args:
        callback_ctx: The context object for the callback.

    Returns:
        A dictionary containing the input mapping for the LLM ask task.
    """
    data = callback_ctx.xcom.ask_trigger.pop()
    system_prompt = callback_ctx.input.system_prompt
    if system_prompt is None or system_prompt.strip() == "":
        system_prompt = llm_config.default_interactive_system_prompt
    return {
        "model": callback_ctx.input.model,
        "base-url": callback_ctx.input.base_url,
        "api-key": callback_ctx.input.api_key,
        "system-prompt": system_prompt,
        "start-new": data.get("start_new"),
        "previous-session": data.get("previous_session_name"),
        "message": data.get("message"),
        "modes": data.get("modes"),
        "yolo": data.get("yolo"),
    }


async def _trigger_ask(
    ctx: AnyContext,
    user_prompt: str,
    modes: str,
    yolo_mode: bool | str,
    previous_session_name: str | None = None,
    start_new: bool = False,
):
    """
    Triggers the LLM ask task by pushing data to the 'ask_trigger' XCom queue.

    Args:
        ctx: The context object for the task.
        user_prompt: The user's message to send to the LLM.
        previous_session_name: The name of the previous chat session (optional).
        start_new: Whether to start a new conversation (optional).
    """
    if previous_session_name is None:
        previous_session_name = await _wait_ask_session_name(ctx)
    ctx.xcom["ask_trigger"].push(
        {
            "previous_session_name": previous_session_name,
            "start_new": start_new,
            "message": user_prompt,
            "modes": modes,
            "yolo": yolo_mode,
        }
    )


async def _wait_ask_result(ctx: AnyContext) -> str | None:
    """
    Waits for and retrieves the LLM task result from the 'ask_result' XCom queue.

    Args:
        ctx: The context object for the task.

    Returns:
        The result string from the LLM task.
    """
    while "ask_result" not in ctx.xcom or len(ctx.xcom.ask_result) == 0:
        await asyncio.sleep(0.1)
        if "ask_error" in ctx.xcom and len(ctx.xcom.ask_error) > 0:
            ctx.xcom.ask_error.pop()
            return None
    return ctx.xcom.ask_result.pop()


async def _wait_ask_session_name(ctx: AnyContext) -> str:
    """
    Waits for and retrieves the LLM chat session name from the 'ask_session_name' XCom queue.

    Args:
        ctx: The context object for the task.

    Returns:
        The session name string.
    """
    while "ask_session_name" not in ctx.xcom or len(ctx.xcom.ask_session_name) == 0:
        await asyncio.sleep(0.1)
    return ctx.xcom.ask_session_name.pop()
