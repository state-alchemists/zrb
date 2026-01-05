import asyncio
import sys
from typing import TYPE_CHECKING, Any

from zrb.builtin.llm.chat_session_cmd import (
    ATTACHMENT_CMD,
    HELP_CMD,
    LOAD_CMD,
    MULTILINE_END_CMD,
    MULTILINE_START_CMD,
    QUIT_CMD,
    RESPONSE_CMD,
    RUN_CLI_CMD,
    SAVE_CMD,
    SESSION_CMD,
    WORKFLOW_CMD,
    YOLO_CMD,
    get_new_attachments,
    get_new_workflows,
    get_new_yolo_mode,
    handle_response_cmd,
    handle_session,
    is_command_match,
    print_commands,
    print_current_attachments,
    print_current_workflows,
    print_current_yolo_mode,
    run_cli_command,
)
from zrb.builtin.llm.chat_trigger import llm_chat_trigger
from zrb.builtin.llm.history import get_last_session_name
from zrb.builtin.llm.xcom_names import (
    LLM_ASK_ERROR_XCOM_NAME,
    LLM_ASK_RESULT_XCOM_NAME,
    LLM_ASK_SESSION_XCOM_NAME,
)
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.workflow import get_llm_loaded_workflow_xcom
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
    current_workflows: str = ctx.input.workflow
    current_yolo_mode: bool | str = ctx.input.yolo
    current_attachments: str = ctx.input.attach
    user_inputs: list[str] = []
    final_result: str = ""
    should_end = False
    start_new: bool = ctx.input.start_new
    if not start_new and ctx.input.previous_session == "":
        session = ctx.session
        if session is not None:
            # Automatically inject last session name as previous session
            last_session_name = get_last_session_name()
            session.shared_ctx.input["previous_session"] = last_session_name
            session.shared_ctx.input["previous-session"] = last_session_name
    current_session_name: str | None = ctx.input.previous_session
    while not should_end:
        await asyncio.sleep(0.01)
        if is_first_time and ctx.input.message.strip() != "":
            user_input = ctx.input.message
        else:
            # Get user input based on mode
            if not multiline_mode:
                ctx.print("💬 >>", plain=True)
            user_input = await llm_chat_trigger.wait(
                ctx, reader, current_session_name, is_first_time
            )
            if not multiline_mode:
                ctx.print("", plain=True)
        # At this point, is_first_time has to be False
        if is_first_time:
            is_first_time = False
        # Add additional workflows activated by LLM in the previous session
        current_workflows = _get_new_workflows_from_xcom(ctx, current_workflows)
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
            elif is_command_match(user_input, RESPONSE_CMD):
                handle_response_cmd(ctx, user_input, final_result)
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
                await run_cli_command(ctx, user_input)
                continue
            elif is_command_match(user_input, HELP_CMD):
                print_commands(ctx)
                continue
            elif (
                is_command_match(user_input, SESSION_CMD)
                or is_command_match(user_input, SAVE_CMD)
                or is_command_match(user_input, LOAD_CMD)
            ):
                current_session_name, start_new = handle_session(
                    ctx, current_session_name, start_new, user_input
                )
            else:
                user_inputs.append(user_input)
        # Trigger LLM
        user_prompt = "\n".join(user_inputs)
        user_inputs = []
        result, current_session_name = await _trigger_ask_and_wait_for_result(
            ctx=ctx,
            user_prompt=user_prompt,
            attach=current_attachments,
            workflows=current_workflows,
            yolo_mode=current_yolo_mode,
            previous_session_name=current_session_name,
            start_new=start_new,
        )
        # After the first trigger, we no longer need to force start_new
        start_new = False
        current_attachments = ""
        final_result = final_result if result is None else result
        if ctx.is_web_mode or not is_tty:
            return final_result
    return final_result


def _get_new_workflows_from_xcom(ctx: AnyContext, current_workflows: str):
    llm_loaded_workflow_xcom = get_llm_loaded_workflow_xcom(ctx)
    new_workflow_names = [
        workflow_name.strip()
        for workflow_name in current_workflows.split(",")
        if workflow_name.strip() != ""
    ]
    while len(llm_loaded_workflow_xcom) > 0:
        additional_workflow_names = [
            workflow_name
            for workflow_name in llm_loaded_workflow_xcom.pop()
            if workflow_name not in new_workflow_names
        ]
        new_workflow_names += additional_workflow_names
    return ",".join(new_workflow_names)


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
) -> tuple[str | None, str | None]:
    """
    Triggers the LLM ask task and waits for the result via XCom.

    Args:
        ctx: The context object for the task.
        user_prompt: The user's message to send to the LLM.
        previous_session_name: The name of the previous chat session (optional).
        start_new: Whether to start a new conversation (optional).

    Returns:
        The result from the LLM task and the session name.
    """
    if user_prompt.strip() == "":
        return None, previous_session_name
    await _trigger_ask(
        ctx, user_prompt, attach, workflows, yolo_mode, previous_session_name, start_new
    )
    result = await _wait_ask_result(ctx)

    resolved_session_name = previous_session_name
    if result is not None:
        resolved_session_name = await _wait_ask_session_name(ctx)

    md_result = render_markdown(result) if result is not None else ""
    ctx.print("\n🤖 >>", plain=True)
    ctx.print(md_result, plain=True)
    ctx.print("", plain=True)
    return result, resolved_session_name


def get_llm_ask_input_mapping(callback_ctx: AnyContext | AnySharedContext):
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
        "workflow": data.get("workflow"),
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
    ctx.xcom["ask_trigger"].push(
        {
            "previous_session_name": previous_session_name,
            "start_new": start_new,
            "message": user_prompt,
            "attach": attach,
            "workflow": workflows,
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
    while (
        LLM_ASK_RESULT_XCOM_NAME not in ctx.xcom
        or len(ctx.xcom[LLM_ASK_RESULT_XCOM_NAME]) == 0
    ):
        await asyncio.sleep(0.1)
        if (
            LLM_ASK_ERROR_XCOM_NAME in ctx.xcom
            and len(ctx.xcom[LLM_ASK_ERROR_XCOM_NAME]) > 0
        ):
            ctx.xcom[LLM_ASK_ERROR_XCOM_NAME].pop()
            return None
    return ctx.xcom[LLM_ASK_RESULT_XCOM_NAME].pop()


async def _wait_ask_session_name(ctx: AnyContext) -> str:
    """
    Waits for and retrieves the LLM chat session name from the 'ask_session_name' XCom queue.

    Args:
        ctx: The context object for the task.

    Returns:
        The session name string.
    """
    while (
        LLM_ASK_SESSION_XCOM_NAME not in ctx.xcom
        or len(ctx.xcom[LLM_ASK_SESSION_XCOM_NAME]) == 0
    ):
        await asyncio.sleep(0.1)
    return ctx.xcom[LLM_ASK_SESSION_XCOM_NAME].pop()
