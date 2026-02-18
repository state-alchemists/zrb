import os
import platform
import shutil
import subprocess
from datetime import datetime
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.util.git import is_inside_git_dir
from zrb.util.markdown import make_markdown_section


def system_context(
    ctx: AnyContext, current_prompt: str, next_handler: Callable[[AnyContext, str], str]
) -> str:
    # Gather information
    now = datetime.now().strftime("%A, %B %d, %Y %H:%M:%S")
    os_info = platform.platform()
    cwd = os.getcwd()
    context_parts = [
        f"- **Current Time**: {now}",
        f"- **Operating System**: {os_info}",
        f"- **Current Directory**: {cwd}",
    ]
    # Tool info
    tool_info = _get_runtime_info()
    if tool_info:
        context_parts.append(
            make_markdown_section("Installed Tools/Programming Languages", tool_info)
        )
    # Git info
    git_info = _get_git_info()
    if git_info:
        context_parts.append(make_markdown_section("Git Repository", git_info))
    # Project files
    project_files = _get_project_files()
    if project_files:
        context_parts.append(
            make_markdown_section("Project Files (Detected)", project_files)
        )
    # Combine sections
    full_context_block = make_markdown_section(
        "System Context (Always Up To Date)", "\n".join(context_parts)
    )
    return next_handler(ctx, f"{current_prompt}\n\n{full_context_block}")


def _get_project_files() -> str:
    # Define file categories for semantic grouping
    file_categories = {
        "Documentation": ["README.md", "AGENTS.md", "CLAUDE.md"],
        "Python": ["pyproject.toml", "requirements.txt", "setup.py"],
        f"{CFG.ROOT_GROUP_NAME}": [f"{CFG.ROOT_GROUP_NAME}_init.py"],
        "JavaScript/Node.js": [
            "package.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "webpack.config.js",
            "babel.config.js",
        ],
        "Go": ["go.mod", "go.sum"],
        "Rust": ["Cargo.toml", "Cargo.lock"],
        "Java": ["pom.xml", "build.gradle"],
        "Ruby": ["Gemfile", "Rakefile"],
        "PHP": ["composer.json"],
        "Containerization": ["Dockerfile", "docker-compose.yml", ".dockerignore"],
        "Infrastructure & CI/CD": ["Makefile", ".gitlab-ci.yml", ".travis.yml"],
        "Configuration": [".env", "template.env"],
    }

    found_by_category = {}
    for category, files in file_categories.items():
        found = [f for f in files if os.path.exists(f)]
        if found:
            found_by_category[category] = found

    if not found_by_category:
        return ""

    # Format the output
    output_lines = []
    for category, files in found_by_category.items():
        files_str = ", ".join(files)
        output_lines.append(f"  - **{category}**: {files_str}")

    return "\n" + "\n".join(output_lines)


def _get_runtime_info() -> str:
    tools = [
        ("Docker", "docker", ["--version"]),
        ("Node.js", "node", ["--version"]),
        ("Python", "python", ["--version"]),
        ("Java", "java", ["-version"]),
        ("Go", "go", ["version"]),
        ("Ruby", "ruby", ["--version"]),
        ("PHP", "php", ["--version"]),
        ("GCC", "gcc", ["--version"]),
    ]

    info_lines = []
    for label, cmd, args in tools:
        version = _get_tool_version(cmd, args)
        if version:
            info_lines.append(f"- **{label}**: {version}")

    return "\n".join(info_lines)


def _get_tool_version(cmd: str, args: list[str]) -> str:
    if not shutil.which(cmd):
        return ""
    try:
        # Capture both stdout and stderr because some tools (like java) write to stderr
        res = subprocess.run([cmd] + args, capture_output=True, text=True, timeout=1)
        # Note: some tools might exit with non-zero when just asking version (unlikely but possible)
        # or we might want to capture output even if return code is weird, but strict is safer.
        if res.returncode == 0:
            output = res.stdout.strip() or res.stderr.strip()
            if output:
                return output.splitlines()[0]
    except Exception:
        pass
    return ""


def _get_git_info() -> str:
    try:
        # Check if inside git repo
        if not is_inside_git_dir():
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
        return f"- **Branch:** {branch}\n- **Status:** {status_summary}"
    except Exception:
        return ""
