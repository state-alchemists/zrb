import os
import subprocess

from zrb.context.any_context import AnyContext
from zrb.task.llm.workflow import get_available_workflows
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import (
    stylize_blue,
    stylize_bold_yellow,
    stylize_error,
    stylize_faint,
)
from zrb.util.file import write_file
from zrb.util.markdown import make_markdown_section

MULTILINE_START_CMD = ["/multi", "/multiline"]
MULTILINE_END_CMD = ["/end"]
QUIT_CMD = ["/bye", "/quit", "/q", "/exit"]
WORKFLOW_CMD = ["/workflow", "/workflows", "/skill", "/skills", "/w"]
SAVE_CMD = ["/save", "/s"]
ATTACHMENT_CMD = ["/attach", "/attachment", "/attachments"]
YOLO_CMD = ["/yolo"]
HELP_CMD = ["/help", "/info"]
ADD_SUB_CMD = ["add"]
SET_SUB_CMD = ["set"]
CLEAR_SUB_CMD = ["clear"]
RUN_CLI_CMD = ["/run", "/exec", "/execute", "/cmd", "/cli", "!"]


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
        current_attachments_value if current_attachments_value != "" else "*Not Set*"
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
        current_workflows_value
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


def save_final_result(ctx: AnyContext, user_input: str, final_result: str) -> None:
    save_path = get_command_param(user_input, SAVE_CMD)
    save_path = os.path.expanduser(save_path)
    if os.path.exists(save_path):
        ctx.print(
            stylize_error(f"Cannot save to existing file: {save_path}"),
            plain=True,
        )
        return
    write_file(save_path, final_result)
    ctx.print(f"Response saved to {save_path}", plain=True)


def run_cli_command(ctx: AnyContext, user_input: str) -> None:
    command = get_command_param(user_input, RUN_CLI_CMD)
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    ctx.print(
        render_markdown(
            "\n".join(
                [
                    make_markdown_section("📤 Stdout", result.stdout, as_code=True),
                    make_markdown_section("🚫 Stderr", result.stderr, as_code=True),
                    make_markdown_section(
                        "🎯 Return code", f"Return Code: {result.returncode}"
                    ),
                ]
            )
        ),
        plain=True,
    )
    ctx.print("", plain=True)


def get_new_yolo_mode(old_yolo_mode: str | bool, user_input: str) -> str | bool:
    new_yolo_mode = get_command_param(user_input, YOLO_CMD)
    if new_yolo_mode != "":
        return new_yolo_mode
    return old_yolo_mode


def get_new_attachments(old_attachment: str, user_input: str) -> str:
    if not is_command_match(user_input, ATTACHMENT_CMD):
        return old_attachment
    if is_command_match(user_input, ATTACHMENT_CMD, SET_SUB_CMD):
        return get_command_param(user_input, ATTACHMENT_CMD, SET_SUB_CMD)
    if is_command_match(user_input, ATTACHMENT_CMD, CLEAR_SUB_CMD):
        return ""
    if is_command_match(user_input, ATTACHMENT_CMD, ADD_SUB_CMD):
        new_attachment = get_command_param(user_input, ATTACHMENT_CMD, ADD_SUB_CMD)
        return ",".join([old_attachment, new_attachment])
    return old_attachment


def get_new_workflows(old_workflow: str, user_input: str) -> str:
    if not is_command_match(user_input, WORKFLOW_CMD):
        return old_workflow
    if is_command_match(user_input, WORKFLOW_CMD, SET_SUB_CMD):
        return get_command_param(user_input, WORKFLOW_CMD, SET_SUB_CMD)
    if is_command_match(user_input, WORKFLOW_CMD, CLEAR_SUB_CMD):
        return ""
    if is_command_match(user_input, WORKFLOW_CMD, ADD_SUB_CMD):
        new_workflow = get_command_param(user_input, WORKFLOW_CMD, ADD_SUB_CMD)
        return ",".join([old_workflow, new_workflow])
    return old_workflow


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
                _show_command("/bye", "Quit from chat session"),
                _show_command("/multi", "Start multiline input"),
                _show_command("/end", "End multiline input"),
                _show_command("/attachment", "Show current attachment"),
                _show_subcommand("add", "<new-attachment>", "Attach a file"),
                _show_subcommand(
                    "set", "<attachment1,attachment2,...>", "Attach a file"
                ),
                _show_subcommand("clear", "", "Clear attachment"),
                _show_command("/workflow", "Show active workflows"),
                _show_subcommand("add", "<workflow>", "Add active workflow"),
                _show_subcommand(
                    "set", "<workflow1,workflow2,..>", "Set active workflows"
                ),
                _show_subcommand("clear", "", "Deactivate all workflows"),
                _show_command("/save <file-path>", "Save last response to a file"),
                _show_command("/yolo", "Show current YOLO mode"),
                _show_command_param(
                    "<true | false | tool1,tool2,...>", "Set YOLO mode"
                ),
                _show_command("/run", ""),
                _show_command_param(
                    "<cli-command>", "Run a non-interactive CLI command"
                ),
                _show_command("/help", "Show this message"),
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
