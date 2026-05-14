"""System-context middleware: runs once per prompt build.

Beyond rendering environment facts (OS, cwd, git status, project type, tool
availability), this module performs three auto-injections that bridge prompt
assembly to ambient runtime state:

1. **Session wiring** — reads ``ctx.input.session`` and calls
   ``set_current_tool_session()`` (``zrb.llm.tool.ambient_state``). The
   resulting ``ContextVar`` is what the four todo tools (``WriteTodos``,
   ``GetTodos``, ``UpdateTodo``, ``ClearTodos``) read when called without an
   explicit ``session=`` argument, so they always target the active
   conversation.

2. **Active worktree** — if ``EnterWorktree`` was called, the path is rendered
   as ``- Active worktree: <path>`` in every subsequent system prompt and
   reminds the LLM to pass it as ``cwd`` to ``Bash``. Cleared automatically
   when ``ExitWorktree`` is called. Read via ``get_active_worktree()`` from
   ``zrb.llm.tool.ambient_state``. If the path no longer exists on disk, the
   stale value is cleared on the spot.

3. **Pending todos** — pending and in-progress todos from the current session
   are rendered into the system context so the LLM sees them at the start of
   every turn without needing to call ``GetTodos`` first. Completed and
   cancelled items are omitted.
"""

import glob
import os
import platform
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
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
    # lazy: circular — tool → ui → llm_task → prompt.manager → here.
    from zrb.llm.tool.ambient_state import (
        get_active_worktree,
        set_active_worktree,
        set_current_tool_session,
    )
    from zrb.llm.tool.plan import todo_manager

    try:
        session_name = str(ctx.input.session) if hasattr(ctx, "input") else ""
    except Exception:
        session_name = ""
    session_name = session_name.strip() or "default"
    set_current_tool_session(session_name)

    cwd = os.getcwd()
    home = os.path.expanduser("~")
    inside_git = is_inside_git_dir()  # cached per CWD

    # --- Cached per CWD: project/tool detection (stable for the lifetime of a session) ---
    project_types = _detect_project_types(cwd)
    infra_types = _detect_infra_types(cwd, home)
    found_markers = list(_detect_project_markers(cwd))

    extra_tools: list[tuple[str, str]] = []
    for pt in project_types:
        if pt in _PROJECT_TOOLS:
            extra_tools.extend(_PROJECT_TOOLS[pt])
    for it in infra_types:
        if it in _INFRA_TOOLS:
            extra_tools.extend(_INFRA_TOOLS[it])

    found_tools: list[str] = []
    seen_labels: set[str] = set()
    for cmd, label in _DEFAULT_TOOLS + _UTILITY_TOOLS + extra_tools:
        if label not in seen_labels and _which(cmd):  # cached per command
            found_tools.append(label)
            seen_labels.add(label)

    # --- Dynamic: git status and todos always run fresh ---
    git_lines: list[str] = []
    todos_data = None

    if inside_git:
        with ThreadPoolExecutor(max_workers=4) as ex:
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
            f_todos = ex.submit(_safe_get_todos, todo_manager, session_name)

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
            try:
                recent_log = f_git_log.result().stdout.strip()
                if recent_log:
                    log_lines = "\n".join(
                        f"  {line}" for line in recent_log.splitlines()
                    )
                    git_lines.append(f"- Recent commits:\n{log_lines}")
            except Exception:
                pass
            todos_data = f_todos.result()
    else:
        todos_data = _safe_get_todos(todo_manager, session_name)

    # get_active_worktree reads a ContextVar — must run on the caller's thread
    active_wt = get_active_worktree()
    if active_wt and not os.path.isdir(active_wt):
        set_active_worktree("")
        active_wt = ""

    parts = [
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- OS: {platform.platform()}",
        f"- CWD: {cwd}",
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


@lru_cache(maxsize=32)
def _which(cmd: str) -> bool:
    """Check tool availability once per command — tools don't appear/disappear mid-session."""
    return bool(shutil.which(cmd))


@lru_cache(maxsize=8)
def _detect_project_markers(cwd: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            label
            for marker, label in _PROJECT_MARKERS
            if os.path.exists(os.path.join(cwd, marker))
        )
    )


@lru_cache(maxsize=8)
def _detect_project_types(cwd: str) -> tuple[str, ...]:
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
            if glob.glob(os.path.join(cwd, marker)):
                found.append(lang)
                seen.add(lang)
        elif os.path.exists(os.path.join(cwd, marker)):
            found.append(lang)
            seen.add(lang)
    return tuple(found)


@lru_cache(maxsize=8)
def _detect_infra_types(cwd: str, home: str) -> tuple[str, ...]:
    found: list[str] = []
    if glob.glob(os.path.join(cwd, "*.tf")) or os.path.isdir(
        os.path.join(cwd, ".terraform")
    ):
        found.append("Terraform")
    k8s_markers = ("Chart.yaml", "k8s", "kubernetes", "manifests")
    if any(os.path.exists(os.path.join(cwd, m)) for m in k8s_markers):
        found.append("Kubernetes")
    try:
        if os.path.isdir(os.path.join(home, ".aws")):
            found.append("AWS")
        if os.path.isdir(os.path.join(home, ".config", "gcloud")):
            found.append("GCP")
        if os.path.isdir(os.path.join(home, ".azure")):
            found.append("Azure")
    except Exception:
        pass
    return tuple(found)
