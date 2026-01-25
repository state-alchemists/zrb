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

    context_parts = [
        f"- **Current Time**: {now}",
        f"- **Operating System**: {os_info}",
        f"- **Current Directory**: {cwd}",
    ]

    git_info = _get_git_info()
    if git_info:
        context_parts.append(f"\n### Git Repository\n{git_info}")

    # Combine sections
    full_context_block = make_markdown_section(
        "System Context", "\n".join(context_parts)
    )
    return next_handler(ctx, f"{current_prompt}\n\n{full_context_block}")


def _get_git_info() -> str:
    try:
        # Check if inside git repo
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
            f"- **Branch:** {branch}\n"
            f"- **Status:** {status_summary}\n"
            "- **Rules:**\n"
            "  - **NEVER** stage or commit your changes unless explicitly instructed.\n"
            "  - When asked to commit, always gather info first: `git status && git diff HEAD`.\n"
            "  - Always propose a draft commit message."
        )
    except Exception:
        return ""
