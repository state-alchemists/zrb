import glob
import os
import platform
import shutil
import subprocess
from datetime import datetime
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.util.git import is_inside_git_dir


def system_context(
    ctx: AnyContext, current_prompt: str, next_handler: Callable[[AnyContext, str], str]
) -> str:
    parts = [
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- OS: {platform.platform()}",
        f"- CWD: {os.getcwd()}",
    ]

    # Detect project type from markers
    project_types = _detect_project_types()

    # Show relevant runtime tools based on project type
    # Always check these regardless of project type
    default_tools = [
        ("docker", "Docker"),
        ("python", "Python"),
        ("node", "Node"),
        ("go", "Go"),
    ]
    # Additional tools to check if project type detected
    project_tools: dict[str, list[tuple[str, str]]] = {
        "Rust": [("cargo", "Cargo")],
        "Java": [("java", "Java"), ("mvn", "Maven"), ("gradle", "Gradle")],
        "Ruby": [("ruby", "Ruby"), ("bundle", "Bundler")],
        "PHP": [("php", "PHP")],
        "C/C++": [("gcc", "GCC"), ("clang", "Clang"), ("cmake", "CMake")],
        "C#": [("dotnet", ".NET")],
    }
    tools_to_check = default_tools.copy()
    for pt in project_types:
        if pt in project_tools:
            tools_to_check.extend(project_tools[pt])

    found_tools = []
    for cmd, label in tools_to_check:
        if shutil.which(cmd):
            found_tools.append(label)
    if found_tools:
        parts.append(f"- Tools: {', '.join(found_tools)}")

    # Git info
    if is_inside_git_dir():
        try:
            branch = (
                subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()
                or "(detached)"
            )
            status = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            status_str = (
                "Clean" if not status else f"Dirty ({len(status.splitlines())} changes)"
            )
            parts.append(f"- Git: {branch} ({status_str})")
        except Exception:
            pass

    # Project files
    project_markers = [
        ("pyproject.toml", "Python"),
        ("requirements.txt", "Python"),
        ("setup.py", "Python"),
        ("go.mod", "Go"),
        ("Cargo.toml", "Rust"),
        ("package.json", "Node"),
        ("pnpm-lock.yaml", "PNPM"),
        ("yarn.lock", "Yarn"),
        ("Gemfile", "Ruby"),
        ("composer.json", "PHP"),
        ("pom.xml", "Java"),
        ("build.gradle", "Java"),
        ("Makefile", "Make"),
        ("CMakeLists.txt", "C/C++"),
        ("Dockerfile", "Docker"),
        ("docker-compose.yml", "Docker Compose"),
        ("README.md", "Docs"),
        ("AGENTS.md", "Agents"),
    ]
    found_markers = list(
        dict.fromkeys(
            label for marker, label in project_markers if os.path.exists(marker)
        )
    )
    if found_markers:
        parts.append(f"- Project: {', '.join(found_markers)}")

    context_block = "# System Context\n" + "\n".join(parts)
    return next_handler(ctx, f"{current_prompt}\n\n{context_block}")


def _detect_project_types() -> list[str]:
    """Detect project types from existing files."""
    markers = [
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
        ("pom.xml", "Java"),
        ("build.gradle", "Java"),
        ("Gemfile", "Ruby"),
        ("composer.json", "PHP"),
        ("CMakeLists.txt", "C/C++"),
        ("*.sln", "C#"),
        ("*.csproj", "C#"),
    ]
    found: list[str] = []
    seen: set[str] = set()
    for marker, lang in markers:
        if lang in seen:
            continue
        if marker.startswith("*"):
            if glob.glob(marker):
                found.append(lang)
                seen.add(lang)
        elif os.path.exists(marker):
            found.append(lang)
            seen.add(lang)
    return found
