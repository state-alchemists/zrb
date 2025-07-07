"""
This module provides functions for managing interactive chat sessions with an LLM.

It handles reading user input, triggering the LLM task, and managing the
conversation flow via XCom.
"""

import asyncio

from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_bold_yellow, stylize_faint


async def read_user_prompt(ctx: AnyContext) -> str:
    """
    Reads user input from the CLI for an interactive chat session.

    Handles special commands like /bye, /multi, /end, and /help.
    Triggers the LLM task and waits for the result.

    Args:
        ctx: The context object for the task.

    Returns:
        The final result from the LLM session.
    """
    from prompt_toolkit import PromptSession

    _show_info(ctx)
    final_result = ""
    ctx.print("💬 >>", plain=True)
    ctx.print(ctx.input.message, plain=True)
    ctx.print("", plain=True)
    result = await _trigger_ask_and_wait_for_result(
        ctx,
        user_prompt=ctx.input.message,
        previous_session_name=ctx.input.previous_session,
        start_new=ctx.input.start_new,
    )
    if result is not None:
        final_result = result
    if ctx.env.get("_ZRB_WEB_ENV", "0") != "0":
        # On web environment this won't be interactive
        return final_result
    multiline_mode = False
    user_inputs = []
    user_input_session = PromptSession()
    while True:
        await asyncio.sleep(0.01)
        if not multiline_mode:
            ctx.print("💬 >>", plain=True)
        user_input = await user_input_session.prompt_async()
        if not multiline_mode:
            ctx.print("", plain=True)
        # Handle special input
        if user_input.strip().lower() in ("/bye", "/quit", "/q", "/exit"):
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
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
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
            if result is not None:
                final_result = result
        elif user_input.strip().lower() in ("/help", "/info"):
            _show_info(ctx)
            continue
        else:
            user_inputs.append(user_input)
            if multiline_mode:
                continue
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
            if result is not None:
                final_result = result
    return final_result


async def _trigger_ask_and_wait_for_result(
    ctx: AnyContext,
    user_prompt: str,
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
    await _trigger_ask(ctx, user_prompt, previous_session_name, start_new)
    result = await _wait_ask_result(ctx)
    md_result = _render_markdown(result) if result is not None else ""
    ctx.print("\n🤖 >>", plain=True)
    ctx.print(md_result, plain=True)
    ctx.print("", plain=True)
    return result


def _render_markdown(markdown_text: str) -> str:
    """
    Renders Markdown to a string, ensuring link URLs are visible.
    """
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    markdown = Markdown(markdown_text, hyperlinks=False)
    with console.capture() as capture:
        console.print(markdown)
    return capture.get()


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
    }


async def _trigger_ask(
    ctx: AnyContext,
    user_prompt: str,
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


def _show_info(ctx: AnyContext):
    """
    Displays the available chat session commands to the user.

    Args:
        ctx: The context object for the task.
    """
    ctx.print(
        (
            f"  {stylize_bold_yellow('/bye')}   {stylize_faint('Quit from chat session')}\n"
            f"  {stylize_bold_yellow('/multi')} {stylize_faint('Start multiline input')}\n"
            f"  {stylize_bold_yellow('/end')}   {stylize_faint('End multiline input')}\n"
            f"  {stylize_bold_yellow('/help')}  {stylize_faint('Show this message')}\n"
        ),
        plain=True,
    )
