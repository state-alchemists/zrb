import importlib.util
import subprocess
import sys

from zrb.builtin.group import python_group
from zrb.config.config import CFG
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
    for tool in ["isort", "black"]:
        if importlib.util.find_spec(tool) is None:
            missing.append(tool)
    if missing:
        tools = " and ".join(missing)
        pkg = CFG.ROOT_GROUP_NAME
        msg = (
            f"[SYSTEM SUGGESTION]: {tools} not found. "
            f"Install them with: `pipx inject {pkg} black isort --include-apps` "
            f"or `pip install {pkg}[python]`"
        )
        ctx.print_err(msg)
        raise RuntimeError(msg)
    # Run via the current interpreter so the tools resolve from zrb's own venv
    # even when their binaries are not on PATH (e.g. pipx installs).
    for cmd_parts in [
        ["isort", ".", "--profile", "black", "--force-grid-wrap", "0"],
        ["black", "."],
    ]:
        result = subprocess.run(
            [sys.executable, "-m", *cmd_parts], capture_output=True, text=True
        )
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
