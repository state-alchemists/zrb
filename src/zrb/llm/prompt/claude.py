from functools import lru_cache
from pathlib import Path
from typing import Callable

from zrb.context.any_context import AnyContext
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.util.markdown import make_markdown_section


def build_skill_replacements(
    skill_manager: SkillManager,
    active_skills: list[str] | None = None,
) -> dict[str, str]:
    """Compute the placeholder values mandate.md substitutes into its Skill
    Activation section, so the skill catalogue lives there instead of a separate
    ``claude_skills`` prompt section.

    Returns ``{CORE_SKILLS}``, ``{AVAILABLE_SKILLS}``, ``{PREACTIVATED_SKILLS}``:

    - ``CORE_SKILLS`` — the always-on methodology baseline (built-in skills
      under ``llm_plugin/core_skills/``), as a bullet list.
    - ``AVAILABLE_SKILLS`` — every other model-invocable skill (user, project,
      plugin), as a bullet list **under its own heading**, or ``""`` when there
      are none. The heading rides here rather than sitting literally in
      ``workflow.md`` because a stock install has no such skills: every built-in
      utility skill under ``llm_plugin/skills/`` is ``disable-model-invocation``
      (it is a slash command, reached by the user). A literal heading would
      render over ``_(none registered)_``, and paying for a heading that
      introduces nothing teaches the model that catalogue entries are
      decorative.
    - ``PREACTIVATED_SKILLS`` — full content of any pre-activated skills, loaded up
      front; empty when none. Active skills are dropped from the two lists above
      so the model is not told to activate something already loaded.
    """
    active = set(active_skills or [])
    core: list[Skill] = []
    other: list[Skill] = []
    for skill in skill_manager.get_skills():
        if not skill.model_invocable or skill.name in active:
            continue
        (core if _is_core_skill(skill) else other).append(skill)
    available = _format_skill_list(other)
    return {
        "CORE_SKILLS": _format_skill_list(core),
        "AVAILABLE_SKILLS": (
            f"\n### Available Skills\n\n{available}\n" if available else ""
        ),
        "PREACTIVATED_SKILLS": _format_active_skills(skill_manager, active_skills),
    }


def _is_core_skill(skill: Skill) -> bool:
    """A core skill is a built-in shipped under ``llm_plugin/core_skills/``."""
    return "core_skills" in Path(skill.path).parts


def _format_skill_list(skills: list[Skill]) -> str:
    return "\n".join(f"- **{s.name}** — {s.description}" for s in skills)


def _format_active_skills(
    skill_manager: SkillManager, active_skills: list[str] | None
) -> str:
    if not active_skills:
        return ""
    parts: list[str] = []
    for name in active_skills:
        skill = skill_manager.get_skill(name)
        if not (skill and skill.model_invocable):
            continue
        content = skill_manager.get_skill_content(name) or skill.description
        parts.append(make_markdown_section(name, content))
    return make_markdown_section("Active Skills (Fully Loaded)", "\n\n".join(parts))


def create_project_context_prompt():
    def project_context(
        ctx: AnyContext,
        current_prompt: str,
        next_handler: Callable[[AnyContext, str], str],
    ) -> str:
        search_dirs = _get_search_directories()

        doc_files: dict[str, list[Path]] = {
            "AGENTS.md": [],
            "CLAUDE.md": [],
            "GEMINI.md": [],
            "README.md": [],
        }

        for directory in search_dirs:
            for filename in doc_files.keys():
                file_path = directory / filename
                if file_path.exists() and file_path.is_file():
                    doc_files[filename].append(file_path)

        # Collect all found file paths, ordered least to most specific, split by
        # scope: a doc sitting in the home directory describes the user's
        # cross-project habits, not this project's rules, so it must not be
        # presented as a project override the mandate forces a full Read of.
        listed_files: list[str] = []
        user_level_files: list[str] = []
        for filename in doc_files.keys():
            for file_path in doc_files[filename]:
                bucket = (
                    user_level_files
                    if _is_user_level_dir(file_path.parent)
                    else listed_files
                )
                bucket.append(f"- `{file_path}`")

        if not listed_files and not user_level_files:
            return next_handler(ctx, current_prompt)

        parts: list[str] = []
        if listed_files:
            parts += [
                "### Documentation Files Found",
                "(See Project Documentation for when to read these.)",
                *listed_files,
            ]
        if user_level_files:
            if parts:
                parts.append("")
            parts += [
                "### User-Level Guidance",
                "(Outside this project — the user's cross-project preferences, not "
                "project rules. Not part of the mandatory read; consult only when "
                "the turn's work depends on it.)",
                *user_level_files,
            ]

        context_message = "\n".join(parts)
        return next_handler(
            ctx,
            f"{current_prompt}\n\n{make_markdown_section('Project Context', context_message)}",
        )

    return project_context


def _is_user_level_dir(directory: Path) -> bool:
    """True when *directory* holds user-level (not project-level) docs.

    Only the home directory itself and ``~/.claude`` qualify: those are the two
    the search path contributes regardless of where the user is working, so a doc
    there is about the user, not the project. Every other entry comes from the
    cwd's parent chain and is genuinely project scoped. Returns ``False`` when
    home cannot be resolved — the mandatory-read bucket is the safe default,
    since that is the pre-split behavior.
    """
    try:
        home = Path.home().resolve()
        resolved = directory.resolve()
    except Exception:
        return False
    return resolved == home or resolved == home / ".claude"


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
