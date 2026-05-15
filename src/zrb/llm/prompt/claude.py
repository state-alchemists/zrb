from functools import lru_cache
from pathlib import Path
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import SkillManager
from zrb.util.markdown import make_markdown_section


def create_claude_skills_prompt(
    skill_manager: SkillManager,
    active_skills: list[str] | None = None,
):
    def claude_compatibility(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()
        additional_context = []

        # 1. Available Claude Skills
        skills_section = _get_skills_section(
            skill_manager,
            search_dirs,
            active_skills=active_skills,
        )
        if skills_section:
            additional_context.append(skills_section)

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility


def _load_file_content(file_path: Path) -> tuple[str, str]:
    """Load file content and return (content, status).

    Cached by ``(path, mtime)`` so per-turn re-reads of unchanged AGENTS.md /
    CLAUDE.md / etc. only pay a single stat call.
    """
    try:
        mtime = file_path.stat().st_mtime
    except OSError:
        return "", "exists (unreadable)"
    return _load_file_content_cached(str(file_path), mtime)


@lru_cache(maxsize=64)
def _load_file_content_cached(path_str: str, mtime: float) -> tuple[str, str]:
    """Cached read. Key includes mtime so edits invalidate the cache."""
    try:
        with open(path_str, "r", encoding="utf-8") as f:
            content = f.read()
            if content.strip():
                return content, "loaded"
            return "", "exists (empty)"
    except Exception:
        return "", "exists (unreadable)"


def create_project_context_prompt():
    def project_context(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()

        # Find all doc files - collect all occurrences, not just first
        doc_files = {
            "AGENTS.md": [],
            "CLAUDE.md": [],
            "GEMINI.md": [],
            "README.md": [],
            "RTK.md": [],
        }

        for directory in search_dirs:
            for filename in doc_files.keys():
                file_path = directory / filename
                if file_path.exists() and file_path.is_file():
                    content, status = _load_file_content(file_path)
                    doc_files[filename].append((file_path, content))

        # Load content from most specific (closest to CWD = last in search_dirs)
        loaded_docs: list[tuple[str, str]] = []  # (section header, content)
        listed_files: list[str] = []

        # README.md is a fallback — skip it when AGENTS.md is available
        agents_has_content = bool(doc_files["AGENTS.md"])

        for filename in doc_files.keys():
            if filename == "README.md" and agents_has_content:
                break
            occurrences = doc_files[filename]
            if not occurrences:
                continue

            # Load from most specific (last occurrence)
            most_specific_path, content = occurrences[-1]
            loaded_content = content[: CFG.LLM_PROJECT_DOC_MAX_CHARS] if content else ""

            if loaded_content:
                loaded_docs.append((filename, loaded_content))

            # List all occurrences
            for path, _ in occurrences:
                listed_files.append(f"- `{path}`")

        if not loaded_docs and not listed_files:
            return next_handler(ctx, current_prompt)

        # Build prompt
        parts = []

        if loaded_docs:
            parts.append("## Project Documentation (Loaded)\n")
            for filename, content in loaded_docs:
                parts.append(f"### {filename}\n{content}\n")

        if listed_files:
            parts.append(
                "## All Documentation Files\n" + "\n".join(listed_files) + "\n\n"
                "**NOTE:** Only the most specific files above are loaded. "
                "Read other files with `Read` tool when needed."
            )

        context_message = "\n".join(parts)
        return next_handler(
            ctx,
            f"{current_prompt}\n\n{make_markdown_section('Project Documentation', context_message)}",
        )

    return project_context


def _get_search_directories() -> list[Path]:
    try:
        home_str = str(Path.home())
    except Exception:
        home_str = ""
    try:
        cwd_str = str(Path.cwd())
    except Exception:
        cwd_str = ""
    return [Path(p) for p in _get_search_directories_cached(home_str, cwd_str)]


@lru_cache(maxsize=8)
def _get_search_directories_cached(home_str: str, cwd_str: str) -> tuple[str, ...]:
    """Compute the project-doc search path once per (home, cwd) pair.

    Returned as a tuple of strings so the cache key/value are hashable. The
    walk is pure: walking the parent chain produces the same list every
    invocation in a session, so caching has no correctness risk.
    """
    dirs: list[str] = []
    if home_str:
        dirs.append(str(Path(home_str) / ".claude"))
    if cwd_str:
        cwd = Path(cwd_str)
        # Parents returns [parent, grandparent...]. We want reversed (Root first)
        # so specific configs (closer to CWD) override general ones.
        for parent in reversed(list(cwd.parents)):
            dirs.append(str(parent))
        dirs.append(str(cwd))
    return tuple(dirs)


def _get_skills_section(
    skill_manager: SkillManager,
    search_dirs: list[Path],
    active_skills: list[str] | None = None,
) -> str | None:
    skills = skill_manager.get_skills()
    if not skills:
        return None

    skills_context = []

    # Add active skills first (if any) with their full content
    if active_skills:
        skills_context.append("## Active Skills (Fully Loaded)")
        for skill_name in active_skills:
            skill_obj = skill_manager.get_skill(skill_name)
            if skill_obj and skill_obj.model_invocable:
                # Get the full skill content
                skill_content = skill_manager.get_skill_content(skill_name)
                if skill_content:
                    skills_context.append(f"### {skill_name}")
                    skills_context.append(skill_content)
                else:
                    # Fallback to description if content can't be loaded
                    skills_context.append(f"- {skill_name}: {skill_obj.description}")
        skills_context.append("")  # Add empty line for separation

    # Add available skills (just metadata)
    skills_context.append(
        "## Available Skills\n"
        "Skills may include companion files (scripts, docs, data). "
        "Activate a skill to see its directory path and companion file listing._"
    )
    for skill in skills:
        if skill.model_invocable:
            # Skip skills that are already active
            if active_skills and skill.name in active_skills:
                continue
            skills_context.append(f"- {skill.name}: {skill.description}")

    return make_markdown_section(
        "Available Skills (Claude Skills)", "\n".join(skills_context)
    )
