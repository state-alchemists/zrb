import os
import platform
import re

from zrb.builtin.group import llm_group
from zrb.config.helper import get_current_shell, is_wsl
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.llm.agent import create_agent
from zrb.llm.config.config import llm_config
from zrb.llm.util.clipboard import copy_text
from zrb.runner.cli import cli
from zrb.task.make_task import make_task
from zrb.util.cli.style import (
    stylize_faint,
    stylize_green,
    stylize_red,
    stylize_yellow,
)

SYSTEM_PROMPT = """
You translate a user's intent into a single shell command.
Respond with the command ONLY. No explanation, no markdown, no code fences.
Prefer built-in commands available on the user's platform and shell.
If the intent cannot be expressed as a single command, respond with the
closest single command that accomplishes the most essential part.
""".strip()


@make_task(
    name="please",
    input=[
        StrInput(
            name="message",
            description="Natural language request",
            prompt="What do you want to do?",
        ),
        StrInput(
            name="model",
            description="LLM model",
            allow_empty=True,
            always_prompt=False,
        ),
    ],
    description=(
        "🙏 Translate natural language into a shell command "
        "and copy it to the clipboard"
    ),
    group=llm_group,
)
async def please(ctx: AnyContext) -> str:
    ctx.print(stylize_faint(f"🤔 Thinking about: {ctx.input.message}"))
    model = str(ctx.input.model).strip() or llm_config.small_model
    agent = create_agent(model=model, system_prompt=SYSTEM_PROMPT, yolo=True)
    result = await agent.run(build_user_message(str(ctx.input.message)))
    command = strip_code_fences(str(result.output))
    if command == "":
        ctx.print(stylize_red("❌ Could not generate a command"))
        return ""
    ctx.print(stylize_yellow(command))
    if copy_text(command):
        ctx.print(stylize_green("📋 Copied to clipboard"))
    else:
        ctx.print(
            stylize_red(
                "⚠️ Could not access clipboard, please copy the command manually"
            )
        )
    return command


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences and surrounding backticks from LLM output."""
    stripped = text.strip()
    match = re.fullmatch(r"```[\w+-]*\n?(.*?)\n?```", stripped, re.DOTALL)
    if match is not None:
        stripped = match.group(1).strip()
    return stripped.strip("`").strip()


def build_user_message(message: str) -> str:
    """Compose the user message containing intent and runtime context."""
    return "\n".join(
        [
            "Environment:",
            f"- Platform: {get_platform_description()}",
            f"- Shell: {get_current_shell()}",
            f"- Working directory: {os.getcwd()}",
            "",
            f"Intent: {message}",
        ]
    )


def get_platform_description() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macOS"
    if system == "Windows":
        return "Windows"
    if is_wsl():
        return "Linux (WSL, Windows commands available via interop)"
    return "Linux"


# Register top-level alias so both `zrb llm please` and `zrb please` work
cli.add_task(please)
