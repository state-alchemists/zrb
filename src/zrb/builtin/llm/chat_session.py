import asyncio
import sys
from typing import TYPE_CHECKING, Any

from zrb.builtin.llm.chat_session_cmd import (
    ATTACHMENT_CMD,
    HELP_CMD,
    MULTILINE_END_CMD,
    MULTILINE_START_CMD,
    QUIT_CMD,
    RUN_CLI_CMD,
    SAVE_CMD,
    WORKFLOW_CMD,
    YOLO_CMD,
    get_new_attachments,
    get_new_workflows,
    get_new_yolo_mode,
    is_command_match,
    print_commands,
    print_current_attachments,
    print_current_workflows,
    print_current_yolo_mode,
    run_cli_command,
    save_final_result,
)
from zrb.builtin.llm.chat_trigger import llm_chat_trigger
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.util.cli.markdown import render_markdown

if TYPE_CHECKING:
    from asyncio import StreamReader

    from prompt_toolkit import PromptSession


async def read_user_prompt(ctx: AnyContext) -> str:
    """
    Reads user input from the CLI for an interactive chat session.
    Orchestrates the session by calling helper functions.
    """
    print_commands(ctx)
    is_tty: bool = ctx.is_tty
    reader: PromptSession[Any] | StreamReader = await _setup_input_reader(is_tty)
    multiline_mode = False
    is_first_time = True
    current_workflows: str = ctx.input.workflows
    current_yolo_mode: bool | str = ctx.input.yolo
    current_attachments: str = ctx.input.attach
    user_inputs: list[str] = []
    final_result: str = ""
    should_end = False
    while not should_end:
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
        # At this point, is_first_time has to be False
        if is_first_time:
            is_first_time = False
        # Handle user input (including slash commands)
        if multiline_mode:
            if is_command_match(user_input, MULTILINE_END_CMD):
                ctx.print("", plain=True)
                multiline_mode = False
            else:
                user_inputs.append(user_input)
                continue
        else:
            if is_command_match(user_input, QUIT_CMD):
                should_end = True
            elif is_command_match(user_input, MULTILINE_START_CMD):
                multiline_mode = True
                ctx.print("", plain=True)
                continue
            elif is_command_match(user_input, WORKFLOW_CMD):
                current_workflows = get_new_workflows(current_workflows, user_input)
                print_current_workflows(ctx, current_workflows)
                continue
            elif is_command_match(user_input, SAVE_CMD):
                save_final_result(ctx, user_input, final_result)
                continue
            elif is_command_match(user_input, ATTACHMENT_CMD):
                current_attachments = get_new_attachments(
                    current_attachments, user_input
                )
                print_current_attachments(ctx, current_attachments)
                continue
            elif is_command_match(user_input, YOLO_CMD):
                current_yolo_mode = get_new_yolo_mode(current_yolo_mode, user_input)
                print_current_yolo_mode(ctx, current_yolo_mode)
                continue
            elif is_command_match(user_input, RUN_CLI_CMD):
                run_cli_command(ctx, user_input)
                continue
            elif is_command_match(user_input, HELP_CMD):
                print_commands(ctx)
                continue
            else:
                user_inputs.append(user_input)
        # Trigger LLM
        user_prompt = "\n".join(user_inputs)
        user_inputs = []
        result = await _trigger_ask_and_wait_for_result(
            ctx=ctx,
            user_prompt=user_prompt,
            attach=current_attachments,
            workflows=current_workflows,
            yolo_mode=current_yolo_mode,
            previous_session_name=previous_session_name,
            start_new=start_new,
        )
        current_attachments = ""
        final_result = final_result if result is None else result
        if ctx.is_web_mode or not is_tty:
            return final_result
    return final_result


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
    attach: str,
    workflows: str,
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
        ctx, user_prompt, attach, workflows, yolo_mode, previous_session_name, start_new
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
        "attach": data.get("attach"),
        "workflows": data.get("workflows"),
        "yolo": data.get("yolo"),
    }


async def _trigger_ask(
    ctx: AnyContext,
    user_prompt: str,
    attach: str,
    workflows: str,
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
            "attach": attach,
            "workflows": workflows,
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
