import shutil
import subprocess

from zrb.builtin.group import python_group
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task


@make_task(
    name="format-code",
    description="✨ Format Python code",
    group=python_group,
    alias="format",
)
def format_python_code(ctx: AnyContext) -> str:
    missing = []
    for tool, install_hint in [
        ("isort", ""),
        ("black", ""),
    ]:
        if shutil.which(tool) is None:
            missing.append(tool)
    if missing:
        tools = " and ".join(missing)
        msg = (
            f"[SYSTEM SUGGESTION]: {tools} not found. "
            f"Install them with: pipx inject zrb \"zrb[format]\""
        )
        ctx.print_err(msg)
        raise RuntimeError(msg)
    for cmd_parts in [
        ["isort", ".", "--profile", "black", "--force-grid-wrap", "0"],
        ["black", "."],
    ]:
        result = subprocess.run(cmd_parts, capture_output=True, text=True)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout:
            ctx.print(stdout)
        if stderr:
            ctx.print_err(stderr)
        if result.returncode != 0:
            raise RuntimeError(
                f"Command {' '.join(cmd_parts)} failed (exit {result.returncode})"
            )
    return "ok"
