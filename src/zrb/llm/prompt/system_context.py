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
        f"- Token limit: {CFG.LLM_MAX_TOKEN_PER_REQUEST:,} per request",
    ]

    # Detect project type from markers
    project_types = _detect_project_types()

    # Always-available runtime tools
    default_tools = [
        ("docker", "Docker"),
        ("python", "Python"),
        ("node", "Node"),
        ("go", "Go"),
    ]

    # Universal utility tools — always checked regardless of project type
    utility_tools = [
        ("jq", "jq"),
        ("curl", "curl"),
        ("gh", "gh"),
        ("make", "make"),
        ("rg", "rg"),
        ("rtk", "rtk"),
    ]

    # Project-type-specific runtime tools
    project_tools: dict[str, list[tuple[str, str]]] = {
        "Rust": [("cargo", "Cargo")],
        "Java": [("java", "Java"), ("mvn", "Maven"), ("gradle", "Gradle")],
        "Ruby": [("ruby", "Ruby"), ("bundle", "Bundler")],
        "PHP": [("php", "PHP")],
        "C/C++": [("gcc", "GCC"), ("clang", "Clang"), ("cmake", "CMake")],
        "C#": [("dotnet", ".NET")],
    }

    # Infrastructure tools — checked when infra markers are present
    infra_tools: dict[str, list[tuple[str, str]]] = {
        "Terraform": [("terraform", "terraform")],
        "Kubernetes": [("kubectl", "kubectl"), ("helm", "helm")],
        "AWS": [("aws", "aws")],
        "GCP": [("gcloud", "gcloud")],
        "Azure": [("az", "az")],
    }

    tools_to_check = default_tools + utility_tools
    for pt in project_types:
        if pt in project_tools:
            tools_to_check.extend(project_tools[pt])

    infra_types = _detect_infra_types()
    for it in infra_types:
        if it in infra_tools:
            tools_to_check.extend(infra_tools[it])

    # Tool hints: only for tools where the preference/usage is non-obvious.
    # Well-known tools (gh, rg, jq, curl, make) need no explanation — just availability.
    # RTK is new enough to need an explicit usage note.
    _tool_hints: dict[str, str] = {
        "rg": "prefer over grep",
        "jq": "prefer for JSON extraction over ad-hoc parsing",
        "gh": "prefer for GitHub operations (PRs, issues, releases)",
        "rtk": "prefix verbose commands to compress output and save tokens "
        "(e.g. rtk git diff, rtk pytest, rtk grep) — "
        "run `rtk gain` to see savings",
    }

    found_tools = []
    found_hints = []
    seen_labels: set[str] = set()
    for cmd, label in tools_to_check:
        if label not in seen_labels and shutil.which(cmd):
            found_tools.append(label)
            seen_labels.add(label)
            if label in _tool_hints:
                found_hints.append(f"  - {label}: {_tool_hints[label]}")
    if found_tools:
        parts.append(f"- Tools: {', '.join(found_tools)}")
    if found_hints:
        parts.append("- CLI hints:\n" + "\n".join(found_hints))

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
        ("Chart.yaml", "Helm"),
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


def _detect_infra_types() -> list[str]:
    """Detect infrastructure tooling from project markers and home config dirs."""
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
