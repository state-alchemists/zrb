"""
This module provides functions for managing interactive chat sessions with an LLM.

It handles reading user input, triggering the LLM task, and managing the
conversation flow via XCom.
"""

import asyncio

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
    _show_info(ctx)
    final_result = ""
    ctx.print(stylize_faint("🧑 >> ") + f"{ctx.input.message}", plain=True)
    result = await _trigger_ask_and_wait_for_result(
        ctx,
        user_prompt=ctx.input.message,
        previous_session_name=ctx.input.previous_session,
        start_new=ctx.input.start_new,
    )
    if ctx.env.get("_ZRB_WEB_ENV", "0") != "0":
        # Don't run in web environment
        if result is not None:
            final_result = result
        return final_result
    multiline_mode = False
    user_inputs = []
    while True:
        await asyncio.sleep(0.01)
        ctx.print(stylize_faint("🧑 >> "), end="", plain=True)
        user_input = input()
        # Handle special input
        if user_input.strip().lower() in ("/bye", "/quit"):
            user_prompt = "\n".join(user_inputs)
            user_inputs = []
            result = await _trigger_ask_and_wait_for_result(ctx, user_prompt)
            if result is not None:
                final_result = result
            break
        elif user_input.strip().lower() in ("/multi"):
            multiline_mode = True
        elif user_input.strip().lower() in ("/end"):
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
    ctx.print(stylize_faint("🤖 >> ") + result, plain=True)
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
    return {
        "model": callback_ctx.input.model,
        "base-url": callback_ctx.input.base_url,
        "api-key": callback_ctx.input.api_key,
        "system-prompt": callback_ctx.input.system_prompt,
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


async def _wait_ask_result(ctx: AnyContext) -> str:
    """
    Waits for and retrieves the LLM task result from the 'ask_result' XCom queue.

    Args:
        ctx: The context object for the task.

    Returns:
        The result string from the LLM task.
    """
    while "ask_result" not in ctx.xcom or len(ctx.xcom.ask_result) == 0:
        await asyncio.sleep(0.1)
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
        stylize_bold_yellow(
            "\n".join(
                [
                    "/bye:   Quit from chat session",
                    "/multi: Start multiline input",
                    "/end:   End multiline input",
                    "/help:  Show this message",
                ]
            )
        ),
        plain=True,
    )
