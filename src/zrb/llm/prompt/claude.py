from pathlib import Path
from typing import Callable, List, Optional

from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.util.markdown import make_markdown_section


def create_claude_skills_prompt(
    skill_manager: SkillManager, active_skills: Optional[List[str]] = None
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
            skill_manager, search_dirs, active_skills=active_skills
        )
        if skills_section:
            additional_context.append(skills_section)

        new_section = "\n\n".join(additional_context)
        return next_handler(ctx, f"{current_prompt}\n\n{new_section}")

    return claude_compatibility


def create_project_context_prompt():
    def project_context(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()

        # 1. Try to read and inject content directly
        injected_content = []
        total_length = 0

        for filename in ["CLAUDE.md", "AGENTS.md"]:
            content = _get_combined_content(filename, search_dirs)
            if content:
                injected_content.append(f"## Content of {filename}\n{content}")
                total_length += len(content)

        # If content is reasonably small, inject it directly
        if 0 < total_length < 10000:
            return next_handler(
                ctx,
                f"{current_prompt}\n\n{make_markdown_section('Project Documentation (Loaded)', '\n\n'.join(injected_content))}",
            )

        # 2. Fallback: List files if too large or empty (but found)
        # Scan for context files again (since we might have skipped injection due to size)
        found_files = []
        for filename in ["CLAUDE.md", "AGENTS.md"]:
            for directory in search_dirs:
                file_path = directory / filename
                if file_path.exists() and file_path.is_file():
                    found_files.append(f"- `{file_path}`")
                    break  # Stop searching for this file once found

        if not found_files:
            return next_handler(ctx, current_prompt)

        context_message = (
            "The following project documentation files are available. "
            "**YOU MUST READ THEM** using `Read` if you need to understand "
            "project conventions, architectural patterns, or specific guidelines:\n"
            + "\n".join(found_files)
        )

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


def _get_combined_content(filename: str, search_dirs: list[Path]) -> str:
    contents = []
    for directory in search_dirs:
        file_path = directory / filename
        if file_path.exists() and file_path.is_file():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        contents.append(content)
            except Exception:
                pass
    return "\n\n".join(contents)


def _get_skills_section(
    skill_manager: SkillManager,
    search_dirs: list[Path],
    active_skills: Optional[List[str]] = None,
) -> Optional[str]:
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
    skills_context.append("Use 'ActivateSkill' to load instructions for a skill.")
    for skill in skills:
        if skill.model_invocable:
            # Skip skills that are already active
            if active_skills and skill.name in active_skills:
                continue
            skills_context.append(f"- {skill.name}: {skill.description}")

    return make_markdown_section(
        "Available Skills (Claude Skills)", "\n".join(skills_context)
    )
