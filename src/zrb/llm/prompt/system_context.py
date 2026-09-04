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
    found_tools = _resolve_available_tools(
        project_types, infra_types, os.environ.get("PATH", "")
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

    Priority Order rank 1 tells the model to confirm anything destructive or
    irreversible, and nothing else in the prompt says whether "irreversible" is
    even true here — ``LLM_SANDBOX_ENABLED`` defaults to ``False``, so by
    default both enforcement layers (the FS gate in ``agent.gates`` and the OS
    shell wrapper) are off and every write lands on the user's disk. A rule
    whose stakes the model cannot see is a rule it under-applies.

    One branch on purpose, and the *opposite* one to
    :func:`_format_parallel_tool_call_line`: that function announces the rare
    exception, this one announces the risky state. A "you are sandboxed" line
    would be a licence to relax, gated on a config the model cannot verify;
    silence leaves the unconditional rank-1 rule in force, which is the safe
    way to be wrong.

    Session-invariant — the policy is bound once per run, so this belongs with
    the other cached system facts rather than in ``live_context``.
    """
    if get_effective_sandbox_policy().enabled:
        return None
    return (
        "- Sandbox: none — file writes and shell commands take effect on this "
        "machine directly and are not contained."
    )


def _format_parallel_tool_call_line(model: "Any") -> str | None:
    """Announce only the *exception* to the prompt's batch-by-default rule.

    There is no affirmative branch on purpose. The registry resolves
    ``supports_parallel_tool_calls`` to ``True`` for no built-in model — it is a
    deny-list — so an affirmative line gated on it could never render, while
    ``workflow.md`` gated batching on that line appearing. Every model therefore
    read the rule as unsatisfied and serialized its calls. Batching is now the
    unconditional default in the prompt, and this line exists to withdraw it
    from the models known to malform parallel calls.

    Session-invariant (it only changes on ``/model``, which recomposes the
    prompt anyway), so it belongs with the other system facts rather than in a
    section of its own.
    """
    # lazy: zrb internal (heavy via transitive) — not a cycle, verified
    # empirically.
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
    # lazy: zrb internal (heavy via transitive) — not a cycle, verified
    # empirically.
    from zrb.llm.util.capabilities import is_known_model

    if model is None or not is_known_model(model):
        return None
    name = model if isinstance(model, str) else getattr(model, "model_name", "")
    if not name:
        return None
    return f"- Model: {name}"


def _resolve_available_tools(
    project_types: tuple[str, ...], infra_types: tuple[str, ...], path: str
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
        if label not in seen_labels and _which(cmd, path):
            found_tools.append(label)
            seen_labels.add(label)
    return found_tools


@lru_cache(maxsize=32)
def _which(cmd: str, path: str) -> bool:
    """Check tool availability once per (command, PATH) pair.

    `path` is not used in the body — `shutil.which` reads `$PATH` itself — but
    it must stay in the signature, because it is what the answer actually
    depends on and therefore what the cache must be keyed on. Keying on `cmd`
    alone made this the one probe in this module whose key was narrower than
    its inputs, so a caller that changed `$PATH` (or stubbed the lookup) got a
    stale answer forever. The other probes here already key on everything they
    read (`cwd`, `home`), which is why they never had that failure mode.
    """
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
    except Exception as e:
        # Best-effort tooling detection; skip silently if home is unreadable.
        CFG.LOGGER.debug(f"Infra-type detection failed: {e}")
    return tuple(found)
