"""Session-invariant system context, kept byte-stable so the cacheable prompt prefix survives.

Volatile per-turn state lives in ``live_context`` instead.
"""

import glob
import os
import platform
import shutil
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.prompt.live_context import LIVE_CONTEXT_ANCHOR
from zrb.llm.sandbox.state import get_effective_sandbox_policy

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
    """Render the session-invariant facts (OS, CWD, tools, project, model) into the system prompt."""
    cwd = os.getcwd()
    home = os.path.expanduser("~")

    project_types = _detect_project_types(cwd)
    infra_types = _detect_infra_types(cwd, home)
    found_markers = list(_detect_project_markers(cwd))
    # No default: `shutil.which(path=None)` falls back to os.defpath, while
    # "" would match nothing (bpo-35755).
    found_tools = _resolve_available_tools(
        project_types, infra_types, os.environ.get("PATH")
    )

    parts: list[str] = [
        f"- OS: {platform.platform()}",
        f"- CWD: {cwd}",
    ]
    sandbox_line = _format_sandbox_line()
    if sandbox_line:
        parts.append(sandbox_line)
    model_line = _format_model_line(model)
    if model_line:
        parts.append(model_line)
    if found_tools:
        parts.append(f"- Tools: {', '.join(found_tools)}")
    if found_markers:
        parts.append(f"- Project: {', '.join(found_markers)}")

    parallel_line = _format_parallel_tool_call_line(model)
    if parallel_line:
        parts.append(parallel_line)

    context_block = "# System Context\n" + "\n".join(parts)
    context_block += "\n\n" + LIVE_CONTEXT_ANCHOR
    return next_handler(ctx, f"{current_prompt}\n\n{context_block}")


def _format_sandbox_line() -> str | None:
    """State that tool calls reach the real machine, when they do.

    Only the unsandboxed state is announced: a "you are sandboxed" line would
    invite the model to relax its confirm-before-destructive rule.
    """
    if get_effective_sandbox_policy().enabled:
        return None
    return (
        "- Sandbox: none — file writes and shell commands take effect on this "
        "machine directly and are not contained."
    )


def _format_parallel_tool_call_line(model: "Any") -> str | None:
    """Withdraw the prompt's batch-by-default rule for models known to malform parallel calls.

    ``supports_parallel_tool_calls`` is a deny-list, so only ``False`` is acted on.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.util.capabilities import model_capabilities

    supports = model_capabilities.get(model).supports_parallel_tool_calls
    if supports is False:
        return (
            "- Parallel tool calls: NOT supported by this model — issue exactly "
            "one tool call per response. This overrides every batching "
            "instruction elsewhere, in the workflow rules and in any tool "
            "description. Two calls in one response arrive as a single "
            "malformed call with the names concatenated, and both are lost."
        )
    return None


def _format_model_line(model: "Any") -> str | None:
    """Render the "Model: …" identity line for the system context.

    Returns ``None`` when *model* is None or its identifier cannot be
    resolved (e.g. ``MagicMock`` without a real ``model_name``).
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.util.capabilities import is_known_model

    if model is None or not is_known_model(model):
        return None
    name = model if isinstance(model, str) else getattr(model, "model_name", "")
    if not name:
        return None
    return f"- Model: {name}"


@lru_cache(maxsize=8)
def _resolve_available_tools(
    project_types: tuple[str, ...], infra_types: tuple[str, ...], path: str | None
) -> tuple[str, ...]:
    """Resolve the available tool labels by checking project/infra types + PATH.

    Cached here, not per `shutil.which` probe, so `$PATH` is part of the key.
    """
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
        if label not in seen_labels and shutil.which(cmd, path=path):
            found_tools.append(label)
            seen_labels.add(label)
    return tuple(found_tools)


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
    except Exception as e:
        CFG.LOGGER.debug(f"Infra-type detection failed: {e}")
    return tuple(found)
