"""System context, split into a stable half and a volatile half.

``system_context`` renders only session-invariant facts (OS, cwd, detected
project markers, available tools, model identity) into the system prompt, so
the composed prompt stays byte-identical across turns and the cacheable prefix
survives. ``render_live_context`` renders the per-turn volatile state and is
injected into the latest user turn (wrapped as ``<live-context>`` by
``PromptManager.create_live_context``) rather than the system prompt — this is
what makes prompt caching work even though the live state changes every turn.

``render_live_context`` also performs the per-turn auto-injections that bridge
prompt assembly to ambient runtime state:

1. **Session wiring** — reads ``ctx.input.session`` and calls
   ``set_current_tool_session()`` (``zrb.llm.tool.ambient_state``). The
   resulting ``ContextVar`` is what the todo tools (``WriteTodos``,
   ``GetTodos``) read when called without an explicit ``session=`` argument,
   so they always target the active conversation.

2. **Active worktree** — if ``EnterWorktree`` was called, the path is rendered
   as ``- Active worktree: <path>`` in the live-context block and reminds the
   LLM to pass it as ``cwd`` to ``Bash``. Cleared automatically when
   ``ExitWorktree`` is called. Read via ``get_active_worktree()`` from
   ``zrb.llm.tool.ambient_state``. If the path no longer exists on disk, the
   stale value is cleared on the spot.

3. **Pending todos** — pending and in-progress todos from the current session
   are rendered into the live-context block so the LLM sees them at the start
   of every turn without needing to call ``GetTodos`` first. Completed and
   cancelled items are omitted.

4. **Interactive mode** — reads ``ctx.input.interactive`` and calls
   ``set_interactive_mode()``. The resulting ``ContextVar`` is what
   ``ask_user_question`` consults before blocking on stdin; in non-interactive
   runs the tool short-circuits with a ``[SYSTEM SUGGESTION]`` instead.
"""

import glob
import os
import platform
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache
from typing import Any, Callable

from zrb.context.any_context import AnyContext

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


def _collect_git_info(
    todo_manager, session_name: str
) -> tuple[list[str], "dict[str, Any] | None"]:
    """Run git commands and todo fetch in parallel via ThreadPoolExecutor.

    Returns (git_lines, todos_data).  *todos_data* is ``None`` when outside a
    git directory and the todo call itself failed.
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.util.git import is_inside_git_dir

    if not is_inside_git_dir():
        return [], _safe_get_todos(todo_manager, session_name)

    git_lines: list[str] = []
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
                "Clean" if not status else f"Dirty ({len(status.splitlines())} changes)"
            )
            git_lines.append(f"- Git: {branch} ({status_str})")
        except Exception:
            pass
        try:
            recent_log = f_git_log.result().stdout.strip()
            if recent_log:
                log_lines = "\n".join(f"  {line}" for line in recent_log.splitlines())
                git_lines.append(f"- Recent commits:\n{log_lines}")
        except Exception:
            pass
        todos_data = f_todos.result()

    return git_lines, todos_data


def _format_todo_lines(todos_data: "dict[str, Any]") -> list[str]:
    """Format pending/in-progress todos into display lines."""
    lines: list[str] = []
    active = [
        t
        for t in todos_data.get("todos", [])
        if t["status"] in ("pending", "in_progress")
    ]
    if not active:
        return lines
    total = todos_data["total"]
    done = todos_data["completed"]
    lines.append(f"- Todos ({done}/{total} done):")
    for t in active:
        mark = "[>]" if t["status"] == "in_progress" else "[ ]"
        lines.append(f"  {mark} [{t['id']}] {t['content']}")
    return lines


# Anchors the <live-context> contract in the cached system prompt. Stable text
# — costs nothing per turn and never invalidates the cacheable prefix — while
# telling any model (not just ones that learned <system-reminder>) what the
# block is and that the most recent one wins.
_LIVE_CONTEXT_ANCHOR = (
    "Each user turn ends with a <live-context> block describing current runtime "
    "state (time, git, todos, worktree, mode). It is injected automatically — "
    "not written by the user. Treat the most recent <live-context> as "
    "authoritative; earlier ones are stale snapshots from when that turn was "
    "sent."
)


def system_context(
    ctx: AnyContext,
    current_prompt: str,
    next_handler: Callable[[AnyContext, str], str],
    model: "Any" = None,
) -> str:
    """Render the *stable*, session-invariant facts into the system prompt.

    Only content that does not change within a session lives here (OS, CWD,
    detected project markers, available tools, the model identity line), so the
    composed system prompt stays byte-identical across turns and the cacheable
    prefix survives. Volatile per-turn state (time, git, todos, worktree, mode)
    is rendered by ``render_live_context`` and injected into the latest user
    turn instead — see ``PromptManager.create_live_context``.
    """
    cwd = os.getcwd()
    home = os.path.expanduser("~")

    # --- Cached per CWD: project/tool detection ---
    project_types = _detect_project_types(cwd)
    infra_types = _detect_infra_types(cwd, home)
    found_markers = list(_detect_project_markers(cwd))
    found_tools = _resolve_available_tools(project_types, infra_types)

    parts: list[str] = [
        f"- OS: {platform.platform()}",
        f"- CWD: {cwd}",
    ]
    model_line = _format_model_line(model)
    if model_line:
        parts.append(model_line)
    if found_tools:
        parts.append(f"- Tools: {', '.join(found_tools)}")
    if found_markers:
        parts.append(f"- Project: {', '.join(found_markers)}")

    context_block = "# System Context\n" + "\n".join(parts)
    context_block += "\n\n" + _LIVE_CONTEXT_ANCHOR
    return next_handler(ctx, f"{current_prompt}\n\n{context_block}")


def render_live_context(ctx: AnyContext, model: "Any" = None) -> str:
    """Render the volatile per-turn runtime state for ``<live-context>``.

    Performs the per-turn ambient-state wiring as a side effect — session
    binding (so todo tools target the active conversation), interactive-mode
    binding (consulted by ``ask_user_question``), and stale-worktree cleanup —
    then returns the dynamic lines (time, git, worktree, mode, interactivity,
    pending todos). ``PromptManager.create_live_context`` wraps the result and
    the runner appends it to the latest user turn, keeping the system prompt
    byte-stable so prompt caching survives across turns.

    The ``model`` argument is accepted for parity with ``system_context`` but is
    not currently rendered here (the model identity line is a stable fact).
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.tool.ambient_state import (
        get_active_worktree,
        set_active_worktree,
        set_current_tool_session,
        set_interactive_mode,
    )
    from zrb.llm.tool.plan import todo_manager

    try:
        session_name = str(ctx.input.session) if hasattr(ctx, "input") else ""
    except Exception:
        session_name = ""
    session_name = session_name.strip() or "default"
    set_current_tool_session(session_name)

    try:
        interactive_bool = bool(getattr(ctx.input, "interactive", True))
    except Exception:
        interactive_bool = True
    set_interactive_mode(interactive_bool)

    # --- Dynamic: git and todos ---
    git_lines, todos_data = _collect_git_info(todo_manager, session_name)

    # --- Worktree (ContextVar — must run on caller's thread) ---
    active_wt = get_active_worktree()
    if active_wt and not os.path.isdir(active_wt):
        set_active_worktree("")
        active_wt = ""

    parts: list[str] = [
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    parts.extend(git_lines)
    if active_wt:
        parts.append(
            f"- Active worktree: {active_wt} (pass as cwd to Shell/Bash; use absolute paths for Read/Write/Edit/Grep)"
        )
    mode_line = _format_mode_line()
    if mode_line:
        parts.append(mode_line)
    if interactive_bool:
        parts.append("- Interactive: yes (AskUserQuestion is available)")
    else:
        parts.append(
            "- Interactive: no — do not call AskUserQuestion or wait on user "
            "input mid-turn; decide based on the conversation and continue."
        )
    if todos_data:
        try:
            parts.extend(_format_todo_lines(todos_data))
        except Exception:
            pass

    return "\n".join(parts)


def _format_mode_line() -> str | None:
    """Render the agent-mode line, or None in the default mode.

    Only emits when a non-default mode (e.g. PLAN) is active, so the section is
    byte-identical to before unless plan mode is explicitly entered.
    """
    # lazy: permission is a leaf module.
    from zrb.llm.permission.state import AgentMode, get_current_agent_mode

    if get_current_agent_mode() != AgentMode.PLAN:
        return None
    return (
        "- Active mode: PLAN (read-only — edits, shell, and delegation are "
        "blocked). Investigate, then call ExitPlanMode with your plan to resume."
    )


def _format_model_line(model: "Any") -> str | None:
    """Render the "Model: …" identity line for the system context.

    Returns ``None`` when *model* is None or its identifier cannot be
    resolved (e.g. ``MagicMock`` without a real ``model_name``).
    Capability-driven guidance (parallel tool call policy, etc.) lives
    in the Tool Usage Guide via ``get_parallel_tool_call_section`` —
    see ``src/zrb/builtin/llm/chat.py`` for the section-factory wiring.
    """
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.util.capabilities import is_known_model

    if model is None or not is_known_model(model):
        return None
    name = model if isinstance(model, str) else getattr(model, "model_name", "")
    if not name:
        return None
    return f"- Model: {name}"


def _resolve_available_tools(
    project_types: tuple[str, ...], infra_types: tuple[str, ...]
) -> list[str]:
    """Resolve the available tool labels by checking project/infra types + PATH."""
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
        if label not in seen_labels and _which(cmd):
            found_tools.append(label)
            seen_labels.add(label)
    return found_tools


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
