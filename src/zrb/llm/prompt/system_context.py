import os
import platform
import subprocess
from datetime import datetime
from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.util.markdown import make_markdown_section


def system_context(
    ctx: AnyContext, current_prompt: str, next_handler: Callable[[AnyContext, str], str]
) -> str:
    # Gather information
    now = datetime.now().strftime("%A, %B %d, %Y %H:%M:%S")
    os_info = f"{platform.system()} {platform.release()}"
    cwd = os.getcwd()

    git_section = _get_git_context()
    sandbox_section = _get_sandbox_context()

    # Build the main info block
    info_content = "\n".join(
        [
            f"- Current Time: {now}",
            f"- OS: {os_info}",
            f"- Directory: {cwd}",
        ]
    )

    # Combine sections
    full_context_block = make_markdown_section("System Context", info_content)

    if git_section:
        full_context_block += f"\n{git_section}"
    if sandbox_section:
        full_context_block += f"\n{sandbox_section}"

    return next_handler(ctx, f"{current_prompt}\n\n{full_context_block}")


def _get_git_context() -> str:
    try:
        # Check if inside git repo
        # (using command is more reliable than checking .git dir for submodules/worktrees)
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return ""

        # Get basic info
        branch_res = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True
        )
        branch = branch_res.stdout.strip() or "(detached head)"

        status_res = subprocess.run(
            ["git", "status", "--short"], capture_output=True, text=True
        )
        status_summary = (
            "Clean" if not status_res.stdout.strip() else "Dirty (Uncommitted changes)"
        )

        return (
            "\n# Git Repository\n"
            "- The current directory is a Git repository.\n"
            f"- **Branch:** {branch}\n"
            f"- **Status:** {status_summary}\n"
            "- **Rules:**\n"
            "  - **NEVER** stage or commit your changes unless explicitly instructed.\n"
            "  - When asked to commit, always gather info first: "
            "`git status && git diff HEAD`.\n"
            "  - Always propose a draft commit message.\n"
        )
    except Exception:
        return ""


def _get_sandbox_context() -> str:
    if not os.environ.get("SANDBOX"):
        return ""

    return (
        "\n# Sandbox Environment\n"
        "- You are running in a restricted sandbox environment.\n"
        "- Access to files outside the project directory may be limited.\n"
        '- If commands fail with "Operation not permitted", explain '
        "this constraint to the user.\n"
    )
