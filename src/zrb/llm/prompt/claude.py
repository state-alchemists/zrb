from pathlib import Path
from typing import Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.util.markdown import make_markdown_section


def create_claude_skills_prompt(
    skill_manager: SkillManager,
    active_skills: list[str] | None = None,
    include_claude_skills: bool = True,
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
            include_claude_skills=include_claude_skills,
        )
        if skills_section:
            additional_context.append(skills_section)

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility


def _load_file_content(file_path: Path) -> tuple[str, str]:
    """Load file content and return (content, status)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
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

        for filename in doc_files.keys():
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
                f"## All Documentation Files\n" + "\n".join(listed_files) + "\n\n"
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
    search_dirs: list[Path] = []
    # 1. User global config (~/.claude)
    try:
        home = Path.home()
        search_dirs.append(home / ".claude")
    except Exception:
        pass

    # 2. Project directories (Root -> ... -> CWD)
    try:
        cwd = Path.cwd()
        # Parents returns [parent, grandparent...]. We want reversed (Root first)
        # This allows specific configs (closer to CWD) to override general ones
        project_dirs = list(cwd.parents)[::-1] + [cwd]
        search_dirs.extend(project_dirs)
    except Exception:
        pass
    return search_dirs


def _get_skills_section(
    skill_manager: SkillManager,
    search_dirs: list[Path],
    active_skills: list[str] | None = None,
    include_claude_skills: bool = True,
) -> str | None:
    # Use SkillManager's built-in search directories logic
    skills = skill_manager.scan(search_dirs=skill_manager.get_search_directories())
    if not skills:
        return None

    skills_context = []

    # Add active skills first (if any) with their full content
    if active_skills:
        skills_context.append("## Active Skills (Fully Loaded)")
        for skill_name in active_skills:
            skill_obj = skill_manager.get_skill(skill_name)

            if skill_obj and skill_obj.model_invocable:
                if not include_claude_skills and not skill_name.startswith(
                    "core_mandate_"
                ):
                    continue
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
    skills_context.append("## Available Skills")
    for skill in skills:
        if skill.model_invocable:
            if not include_claude_skills and not skill.name.startswith("core_mandate_"):
                continue
            # Skip skills that are already active
            if active_skills and skill.name in active_skills:
                continue
            skills_context.append(f"- {skill.name}: {skill.description}")

    return make_markdown_section(
        "Available Skills (Claude Skills)", "\n".join(skills_context)
    )
