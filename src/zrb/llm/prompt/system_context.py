import glob
import os
import platform
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.util.git import is_inside_git_dir

_DEFAULT_TOOLS: list[tuple[str, str]] = [
    ("docker", "Docker"),
    ("python", "Python"),
    ("node", "Node"),
    ("go", "Go"),
]

_UTILITY_TOOLS: list[tuple[str, str]] = [
    ("jq", "jq"),
    ("curl", "curl"),
    ("gh", "gh"),
    ("make", "make"),
    ("rg", "rg"),
    ("rtk", "rtk"),
]

_PROJECT_TOOLS: dict[str, list[tuple[str, str]]] = {
    "Rust": [("cargo", "Cargo")],
    "Java": [("java", "Java"), ("mvn", "Maven"), ("gradle", "Gradle")],
    "Ruby": [("ruby", "Ruby"), ("bundle", "Bundler")],
    "PHP": [("php", "PHP")],
    "C/C++": [("gcc", "GCC"), ("clang", "Clang"), ("cmake", "CMake")],
    "C#": [("dotnet", ".NET")],
}

_INFRA_TOOLS: dict[str, list[tuple[str, str]]] = {
    "Terraform": [("terraform", "terraform")],
    "Kubernetes": [("kubectl", "kubectl"), ("helm", "helm")],
    "AWS": [("aws", "aws")],
    "GCP": [("gcloud", "gcloud")],
    "Azure": [("az", "az")],
}

_PROJECT_MARKERS: list[tuple[str, str]] = [
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
    ("Chart.yaml", "Helm"),
    ("README.md", "Docs"),
    ("AGENTS.md", "Agents"),
]


def system_context(
    ctx: AnyContext, current_prompt: str, next_handler: Callable[[AnyContext, str], str]
) -> str:
    # Lazy imports to avoid circular dependency (tool → ui → llm_task → prompt.manager → here)
    from zrb.llm.tool.ambient_state import (
        get_active_worktree,
        set_current_tool_session,
    )
    from zrb.llm.tool.plan import todo_manager

    try:
        session_name = str(ctx.input.session) if hasattr(ctx, "input") else ""
    except Exception:
        session_name = ""
    session_name = session_name.strip() or "default"
    set_current_tool_session(session_name)

    inside_git = is_inside_git_dir()

    with ThreadPoolExecutor(max_workers=16) as ex:
        # Submit all independent IO work immediately
        f_project_types = ex.submit(_detect_project_types)
        f_infra_types = ex.submit(_detect_infra_types)
        f_markers = ex.submit(_detect_project_markers)
        f_todos = ex.submit(_safe_get_todos, todo_manager, session_name)

        f_git_branch = f_git_status = f_git_log = None
        if inside_git:
            f_git_branch = ex.submit(
                subprocess.run,
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            f_git_status = ex.submit(
                subprocess.run,
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            f_git_log = ex.submit(
                subprocess.run,
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                timeout=5,
            )

        # Always-checked tools have no dependency on project types — submit immediately
        always_tools = _DEFAULT_TOOLS + _UTILITY_TOOLS
        f_always_which = [
            (cmd, label, ex.submit(shutil.which, cmd)) for cmd, label in always_tools
        ]

        # Project/infra types gate the extra tool checks — wait for them, then submit
        project_types = f_project_types.result()
        infra_types = f_infra_types.result()

        extra_tools: list[tuple[str, str]] = []
        for pt in project_types:
            if pt in _PROJECT_TOOLS:
                extra_tools.extend(_PROJECT_TOOLS[pt])
        for it in infra_types:
            if it in _INFRA_TOOLS:
                extra_tools.extend(_INFRA_TOOLS[it])
        f_extra_which = [
            (cmd, label, ex.submit(shutil.which, cmd)) for cmd, label in extra_tools
        ]

        # Collect which() results in deterministic order
        found_tools: list[str] = []
        seen_labels: set[str] = set()
        for _cmd, label, f in f_always_which + f_extra_which:
            if label not in seen_labels and f.result():
                found_tools.append(label)
                seen_labels.add(label)

        found_markers: list[str] = f_markers.result()
        todos_data = f_todos.result()

        git_lines: list[str] = []
        if inside_git:
            if f_git_branch and f_git_status:
                try:
                    branch = f_git_branch.result().stdout.strip() or "(detached)"
                    status = f_git_status.result().stdout.strip()
                    status_str = (
                        "Clean"
                        if not status
                        else f"Dirty ({len(status.splitlines())} changes)"
                    )
                    git_lines.append(f"- Git: {branch} ({status_str})")
                except Exception:
                    pass
            if f_git_log:
                try:
                    recent_log = f_git_log.result().stdout.strip()
                    if recent_log:
                        log_lines = "\n".join(
                            f"  {line}" for line in recent_log.splitlines()
                        )
                        git_lines.append(f"- Recent commits:\n{log_lines}")
                except Exception:
                    pass

    # get_active_worktree reads a ContextVar — must run on the caller's thread
    active_wt = get_active_worktree()

    # Assemble in the same order as before
    parts = [
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- OS: {platform.platform()}",
        f"- CWD: {os.getcwd()}",
        f"- Token limit: {CFG.LLM_MAX_TOKEN_PER_REQUEST:,} per request",
    ]

    if found_tools:
        parts.append(f"- Tools: {', '.join(found_tools)}")

    parts.extend(git_lines)

    if found_markers:
        parts.append(f"- Project: {', '.join(found_markers)}")

    if active_wt:
        parts.append(
            f"- Active worktree: {active_wt} (pass as cwd to Bash; use absolute paths for Read/Write/Edit/Grep)"
        )

    if todos_data:
        try:
            active = [
                t
                for t in todos_data.get("todos", [])
                if t["status"] in ("pending", "in_progress")
            ]
            if active:
                total = todos_data["total"]
                done = todos_data["completed"]
                todo_lines = [f"- Todos ({done}/{total} done):"]
                for t in active:
                    mark = "[>]" if t["status"] == "in_progress" else "[ ]"
                    todo_lines.append(f"  {mark} [{t['id']}] {t['content']}")
                parts.extend(todo_lines)
        except Exception:
            pass

    context_block = "# System Context\n" + "\n".join(parts)
    return next_handler(ctx, f"{current_prompt}\n\n{context_block}")


def _safe_get_todos(todo_manager, session_name: str):
    try:
        return todo_manager.get_todos(session_name)
    except Exception:
        return None


def _detect_project_markers() -> list[str]:
    return list(
        dict.fromkeys(
            label for marker, label in _PROJECT_MARKERS if os.path.exists(marker)
        )
    )


def _detect_project_types() -> list[str]:
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


def _detect_infra_types() -> list[str]:
    found: list[str] = []
    if glob.glob("*.tf") or os.path.isdir(".terraform"):
        found.append("Terraform")
    k8s_markers = ("Chart.yaml", "k8s", "kubernetes", "manifests")
    if any(os.path.exists(m) for m in k8s_markers):
        found.append("Kubernetes")
    try:
        home = os.path.expanduser("~")
        if os.path.isdir(os.path.join(home, ".aws")):
            found.append("AWS")
        if os.path.isdir(os.path.join(home, ".config", "gcloud")):
            found.append("GCP")
        if os.path.isdir(os.path.join(home, ".azure")):
            found.append("Azure")
    except Exception:
        pass
    return found
