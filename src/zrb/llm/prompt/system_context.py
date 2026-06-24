"""Session-invariant system context rendered into the cached system prompt.

``system_context`` renders only stable facts (OS, cwd, detected project
markers, available tools, model identity) into the system prompt, so the
composed prompt stays byte-identical across turns and the cacheable prefix
survives. The live (volatile) counterpart lives in ``live_context`` and is
injected into the user turn instead — see ``PromptManager.create_live_context``.
"""

import glob
import os
import platform
import shutil
from functools import lru_cache
from typing import Any, Callable

from zrb.context.any_context import AnyContext
from zrb.llm.prompt.live_context import _LIVE_CONTEXT_ANCHOR

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
    ("glab", "glab"),
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
    ("docker-compose.yaml", "Docker Compose"),
    ("Chart.yaml", "Helm"),
]


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
