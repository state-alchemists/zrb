import os
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.task.llm.workflow import get_available_workflows
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import (
    stylize_blue,
    stylize_bold_yellow,
    stylize_error,
    stylize_faint,
)
from zrb.util.cmd.command import run_command
from zrb.util.file import read_file, write_file
from zrb.util.markdown import make_markdown_section
from zrb.util.string.conversion import FALSE_STRS, TRUE_STRS, to_boolean

MULTILINE_START_CMD = ["/multi", "/multiline"]
MULTILINE_END_CMD = ["/end"]
QUIT_CMD = ["/bye", "/quit", "/q", "/exit"]
WORKFLOW_CMD = ["/workflow", "/workflows", "/skill", "/skills", "/w"]
RESPONSE_CMD = ["/response", "/res"]
SAVE_CMD = ["/save", "/s"]
LOAD_CMD = ["/load", "/l"]
ATTACHMENT_CMD = ["/attachment", "/attachments", "/attach"]
YOLO_CMD = ["/yolo"]
HELP_CMD = ["/help", "/info"]
RUN_CLI_CMD = ["/run", "/exec", "/execute", "/cmd", "/cli", "!"]
SESSION_CMD = ["/session", "/conversation", "/convo"]

ADD_SUB_CMD = ["add"]
SET_SUB_CMD = ["set"]
CLEAR_SUB_CMD = ["clear"]
SAVE_SUB_CMD = ["save"]
LOAD_SUB_CMD = ["load"]

# Command display constants
MULTILINE_START_CMD_DESC = "Start multiline input"
MULTILINE_END_CMD_DESC = "End multiline input"
QUIT_CMD_DESC = "Quit from chat session"
WORKFLOW_CMD_DESC = "Show active workflows"
WORKFLOW_ADD_SUB_CMD_DESC = (
    "Add active workflow " f"(e.g., `{WORKFLOW_CMD[0]} {ADD_SUB_CMD[0]} coding`)"
)
WORKFLOW_SET_SUB_CMD_DESC = (
    "Set active workflows "
    f"(e.g., `{WORKFLOW_CMD[0]} {SET_SUB_CMD[0]} coding,researching`)"
)
WORKFLOW_CLEAR_SUB_CMD_DESC = "Deactivate all workflows"
RESPONSE_CMD_DESC = "Manage response"
RESPONSE_SAVE_SUB_CMD_DESC = (
    "Save last response to a file "
    f"(e.g., `{RESPONSE_CMD[0]} {SAVE_SUB_CMD[0]} conclusion.md`)"
)
SAVE_CMD_DESC = "Save current session " f"(e.g., `{SAVE_CMD[0]} save-point`)"
LOAD_CMD_DESC = "Load session " f"(e.g., `{LOAD_CMD[0]} save-point`)"
ATTACHMENT_CMD_DESC = "Show current attachment"
ATTACHMENT_ADD_SUB_CMD_DESC = (
    "Attach a file " f"(e.g., `{ATTACHMENT_CMD[0]} {ADD_SUB_CMD[0]} ./logo.png`)"
)
ATTACHMENT_SET_SUB_CMD_DESC = (
    "Set attachments "
    f"(e.g., `{ATTACHMENT_CMD[0]} {SET_SUB_CMD[0]} ./logo.png,./diagram.png`)"
)
ATTACHMENT_CLEAR_SUB_CMD_DESC = "Clear attachment"
YOLO_CMD_DESC = "Show/manipulate current YOLO mode"
YOLO_SET_CMD_DESC = (
    "Assign YOLO tools "
    f"(e.g., `{YOLO_CMD[0]} {SET_SUB_CMD[0]} read_from_file,analyze_file`)"
)
YOLO_SET_TRUE_CMD_DESC = "Activate YOLO mode for all tools"
YOLO_SET_FALSE_CMD_DESC = "Deactivate YOLO mode for all tools"
RUN_CLI_CMD_DESC = "Run a non-interactive CLI command"
HELP_CMD_DESC = "Show info/help"
SESSION_CMD_DESC = "Show current session"


def print_current_yolo_mode(
    ctx: AnyContext, current_yolo_mode_value: str | bool
) -> None:
    yolo_mode_str = (
        current_yolo_mode_value if current_yolo_mode_value != "" else "*Not Set*"
    )
    ctx.print(render_markdown(f"🎲 Current YOLO mode: {yolo_mode_str}"), plain=True)
    ctx.print("", plain=True)


def print_current_attachments(ctx: AnyContext, current_attachments_value: str) -> None:
    attachments_str = (
        ", ".join(current_attachments_value.split(","))
        if current_attachments_value != ""
        else "*Not Set*"
    )
    ctx.print(render_markdown(f"📎 Current attachments: {attachments_str}"), plain=True)
    ctx.print("", plain=True)


def print_current_workflows(ctx: AnyContext, current_workflows_value: str) -> None:
    available_workflows = get_available_workflows()
    available_workflows_str = (
        ", ".join(sorted([workflow_name for workflow_name in available_workflows]))
        if len(available_workflows) > 0
        else "*No Available Workflow*"
    )
    current_workflows_str = (
        ", ".join(current_workflows_value.split(","))
        if current_workflows_value != ""
        else "*No Active Workflow*"
    )
    ctx.print(
        render_markdown(
            "\n".join(
                [
                    f"- 🔄 Current workflows   : {current_workflows_str}",
                    f"- 📚 Available workflows : {available_workflows_str}",
                ]
            )
        ),
        plain=True,
    )
    ctx.print("", plain=True)


def handle_response_cmd(ctx: AnyContext, user_input: str, final_result: str) -> None:
    if not is_command_match(user_input, RESPONSE_CMD, SAVE_SUB_CMD):
        return
    save_path = get_command_param(user_input, RESPONSE_CMD, SAVE_SUB_CMD)
    save_path = os.path.expanduser(save_path)
    if os.path.exists(save_path):
        ctx.print(
            stylize_error(f"Cannot save to existing file: {save_path}"),
            plain=True,
        )
        return
    write_file(save_path, final_result)
    ctx.print(f"Response saved to {save_path}", plain=True)


async def run_cli_command(ctx: AnyContext, user_input: str) -> None:
    command = get_command_param(user_input, RUN_CLI_CMD)
    cmd_result, return_code = await run_command(
        [CFG.DEFAULT_SHELL, "-c", command],
        print_method=_create_faint_print(ctx),
        timeout=3600,
    )
    ctx.print(
        render_markdown(
            make_markdown_section(
                f"`{command}`",
                "\n".join(
                    [
                        make_markdown_section(
                            "📤 Stdout", cmd_result.output, as_code=True
                        ),
                        make_markdown_section(
                            "🚫 Stderr", cmd_result.error, as_code=True
                        ),
                        make_markdown_section(
                            "🎯 Return code", f"Return Code: {return_code}"
                        ),
                    ]
                ),
            )
        ),
        plain=True,
    )
    ctx.print("", plain=True)


def _create_faint_print(ctx: AnyContext) -> Callable[..., None]:
    def print_faint(text: str):
        ctx.print(stylize_faint(f"  {text}"), plain=True)

    return print_faint


def get_new_yolo_mode(old_yolo_mode: str | bool, user_input: str) -> str | bool:
    if not is_command_match(user_input, YOLO_CMD):
        return old_yolo_mode
    if is_command_match(user_input, YOLO_CMD, SET_SUB_CMD):
        new_yolo_mode = get_command_param(user_input, YOLO_CMD, SET_SUB_CMD)
    else:
        new_yolo_mode = get_command_param(user_input, YOLO_CMD)
    if new_yolo_mode != "":
        if new_yolo_mode in TRUE_STRS or new_yolo_mode in FALSE_STRS:
            return to_boolean(new_yolo_mode)
        return new_yolo_mode
    if isinstance(old_yolo_mode, bool):
        return old_yolo_mode
    return _normalize_comma_separated_str(old_yolo_mode)


def get_new_attachments(old_attachment: str, user_input: str) -> str:
    if not is_command_match(user_input, ATTACHMENT_CMD):
        return _normalize_comma_separated_str(old_attachment)
    if is_command_match(user_input, ATTACHMENT_CMD, SET_SUB_CMD):
        return _normalize_comma_separated_str(
            get_command_param(user_input, ATTACHMENT_CMD, SET_SUB_CMD)
        )
    if is_command_match(user_input, ATTACHMENT_CMD, CLEAR_SUB_CMD):
        return ""
    if is_command_match(user_input, ATTACHMENT_CMD, ADD_SUB_CMD):
        new_attachment = get_command_param(user_input, ATTACHMENT_CMD, ADD_SUB_CMD)
        return _normalize_comma_separated_str(
            ",".join([old_attachment, new_attachment])
        )
    return old_attachment


def get_new_workflows(old_workflow: str, user_input: str) -> str:
    if not is_command_match(user_input, WORKFLOW_CMD):
        return _normalize_comma_separated_str(old_workflow)
    if is_command_match(user_input, WORKFLOW_CMD, SET_SUB_CMD):
        return _normalize_comma_separated_str(
            get_command_param(user_input, WORKFLOW_CMD, SET_SUB_CMD)
        )
    if is_command_match(user_input, WORKFLOW_CMD, CLEAR_SUB_CMD):
        return ""
    if is_command_match(user_input, WORKFLOW_CMD, ADD_SUB_CMD):
        new_workflow = get_command_param(user_input, WORKFLOW_CMD, ADD_SUB_CMD)
        return _normalize_comma_separated_str(",".join([old_workflow, new_workflow]))
    return _normalize_comma_separated_str(old_workflow)


def handle_session(
    ctx: AnyContext,
    current_session_name: str | None,
    current_start_new: bool,
    user_input: str,
) -> tuple[str | None, bool]:
    if is_command_match(user_input, SAVE_CMD):
        save_point = get_command_param(user_input, SAVE_CMD)
        if not save_point:
            ctx.print(render_markdown("️⚠️ Save point name is required."), plain=True)
            return current_session_name, current_start_new
        if not current_session_name:
            ctx.print(
                render_markdown(
                    "⚠️ No active session to save. Please start a conversation first."
                ),
                plain=True,
            )
            return current_session_name, current_start_new
        save_point_path = os.path.join(CFG.LLM_HISTORY_DIR, "save-point", save_point)
        write_file(save_point_path, current_session_name)
        ctx.print(
            render_markdown(
                f"Session saved to save-point: {save_point} ({current_session_name})"
            ),
            plain=True,
        )
        return current_session_name, current_start_new
    if is_command_match(user_input, LOAD_CMD):
        save_point = get_command_param(user_input, LOAD_CMD)
        if not save_point:
            ctx.print(render_markdown("⚠️ Save point name is required."), plain=True)
            return current_session_name, current_start_new
        save_point_path = os.path.join(CFG.LLM_HISTORY_DIR, "save-point", save_point)
        if not os.path.exists(save_point_path):
            ctx.print(
                render_markdown(f"⚠️ Save point '{save_point}' not found."), plain=True
            )
            return current_session_name, current_start_new
        current_session_name = read_file(save_point_path).strip()
        ctx.print(
            render_markdown(f"Loaded session: {current_session_name}"), plain=True
        )
        # When loading a session, we shouldn't start a new one
        return current_session_name, False
    if is_command_match(user_input, SESSION_CMD):
        ctx.print(
            render_markdown(f"Current session: {current_session_name}"), plain=True
        )
        return current_session_name, current_start_new
    return current_session_name, current_start_new


def _normalize_comma_separated_str(comma_separated_str: str) -> str:
    return ",".join(
        [
            workflow_name.strip()
            for workflow_name in comma_separated_str.split(",")
            if workflow_name.strip() != ""
        ]
    )


def get_command_param(user_input: str, *cmd_patterns: list[str]) -> str:
    if not is_command_match(user_input, *cmd_patterns):
        return ""
    parts = [part for part in user_input.split(" ") if part.strip() != ""]
    if len(parts) <= len(cmd_patterns):
        return ""
    params = parts[len(cmd_patterns) :]
    return " ".join(params)


def is_command_match(user_input: str, *cmd_patterns: list[str]) -> bool:
    parts = [part for part in user_input.split(" ") if part.strip() != ""]
    if len(cmd_patterns) > len(parts):
        return False
    for index, cmd_pattern in enumerate(cmd_patterns):
        part = parts[index]
        if part.lower() not in cmd_pattern:
            return False
    return True


def print_commands(ctx: AnyContext):
    """
    Displays the available chat session commands to the user.
    Args:
        ctx: The context object for the task.
    """
    ctx.print(
        "\n".join(
            [
                _show_command(QUIT_CMD[0], QUIT_CMD_DESC),
                _show_command(MULTILINE_START_CMD[0], MULTILINE_START_CMD_DESC),
                _show_command(MULTILINE_END_CMD[0], MULTILINE_END_CMD_DESC),
                _show_command(ATTACHMENT_CMD[0], ATTACHMENT_CMD_DESC),
                _show_subcommand(
                    ADD_SUB_CMD[0], "<file-path>", ATTACHMENT_ADD_SUB_CMD_DESC
                ),
                _show_subcommand(
                    SET_SUB_CMD[0],
                    "<file1-path,file2-path,...>",
                    ATTACHMENT_SET_SUB_CMD_DESC,
                ),
                _show_subcommand(CLEAR_SUB_CMD[0], "", ATTACHMENT_CLEAR_SUB_CMD_DESC),
                _show_command(WORKFLOW_CMD[0], WORKFLOW_CMD_DESC),
                _show_subcommand(
                    ADD_SUB_CMD[0], "<workflow>", WORKFLOW_ADD_SUB_CMD_DESC
                ),
                _show_subcommand(
                    SET_SUB_CMD[0],
                    "<workflow1,workflow2,..>",
                    WORKFLOW_SET_SUB_CMD_DESC,
                ),
                _show_subcommand(CLEAR_SUB_CMD[0], "", WORKFLOW_CLEAR_SUB_CMD_DESC),
                _show_command(SESSION_CMD[0], SESSION_CMD_DESC),
                _show_command(SAVE_CMD[0], SAVE_CMD_DESC),
                _show_command(LOAD_CMD[0], LOAD_CMD_DESC),
                _show_command(RESPONSE_CMD[0], RESPONSE_CMD_DESC),
                _show_subcommand(
                    SAVE_SUB_CMD[0], "<file-path>", RESPONSE_SAVE_SUB_CMD_DESC
                ),
                _show_command(YOLO_CMD[0], YOLO_CMD_DESC),
                _show_subcommand(SET_SUB_CMD[0], "true", YOLO_SET_TRUE_CMD_DESC),
                _show_subcommand(SET_SUB_CMD[0], "false", YOLO_SET_FALSE_CMD_DESC),
                _show_subcommand(
                    SET_SUB_CMD[0], "<tool1,tool2,tool2>", YOLO_SET_CMD_DESC
                ),
                _show_command(RUN_CLI_CMD[0], ""),
                _show_command_param("<cli-command>", RUN_CLI_CMD_DESC),
                _show_command(HELP_CMD[0], HELP_CMD_DESC),
            ]
        ),
        plain=True,
    )
    ctx.print("", plain=True)


def _show_command(command: str, description: str) -> str:
    styled_command = stylize_bold_yellow(command.ljust(37))
    styled_description = stylize_faint(description)
    return f"  {styled_command} {styled_description}"


def _show_subcommand(subcommand: str, param: str, description: str) -> str:
    styled_subcommand = stylize_bold_yellow(f"    {subcommand}")
    styled_param = stylize_blue(param.ljust(32 - len(subcommand)))
    styled_description = stylize_faint(description)
    return f"  {styled_subcommand} {styled_param} {styled_description}"


def _show_command_param(param: str, description: str) -> str:
    styled_param = stylize_blue(f"    {param}".ljust(37))
    styled_description = stylize_faint(description)
    return f"  {styled_param} {styled_description}"
