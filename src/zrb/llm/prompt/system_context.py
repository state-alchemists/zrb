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
    # Time
    now = datetime.now().strftime("%A, %B %d, %Y %H:%M:%S")

    # System
    os_info = f"{platform.system()} {platform.release()}"

    # CWD
    cwd = os.getcwd()

    # Git
    git_info = ""
    try:
        if os.path.isdir(os.path.join(cwd, ".git")):
            # Get branch
            res = subprocess.run(
                ["git", "branch", "--show-current"], capture_output=True, text=True
            )
            if res.returncode == 0:
                branch = res.stdout.strip()
                if branch:
                    git_info = f"\n- Git Branch: {branch}"
    except Exception:
        pass

    info_content = "\n".join(
        [
            f"- Date: {now}",
            f"- OS: {os_info}",
            f"- Directory: {cwd}{git_info}",
        ]
    )
    info_block = make_markdown_section("System Context", info_content)
    return next_handler(ctx, f"{current_prompt}\n\n{info_block}")
