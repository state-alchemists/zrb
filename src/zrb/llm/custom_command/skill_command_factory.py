import re
from collections.abc import Callable
from pathlib import Path

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.custom_command.custom_command import CustomCommand
from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.util import format_companion_file_lines


def get_skill_custom_command(
    skill_manager: SkillManager,
) -> Callable[[], list[AnyCustomCommand]]:
    def factory() -> list[AnyCustomCommand]:
        return _get_skill_custom_commands(skill_manager)

    return factory


def _get_skill_custom_commands(skill_manager: SkillManager) -> list[AnyCustomCommand]:
    commands: list[AnyCustomCommand] = []
    skills = skill_manager.scan()
    for skill in skills:
        if not skill.user_invocable:
            continue
        content = skill_manager.get_skill_content(skill.name)
        if not content:
            continue

        args = _extract_args(content)
        description = skill.description
        if skill.argument_hint:
            description = f"{skill.description} {skill.argument_hint}"
        # Prepend skill context header (directory path + companion files)
        skill_dir = str(Path(skill.path).parent)
        context_lines = [
            f"Skill directory (working directory): {skill_dir}",
            "",
            "All file paths in the instructions below are relative to this directory.",
            "Use companion files (scripts, tools, references) by resolving them against this path.",
        ]
        context_lines.extend(format_companion_file_lines(skill.companion_files))
        context_lines.append("")
        context_lines.append("---")
        prompt_with_companions = "\n".join(context_lines) + "\n\n" + content
        commands.append(
            CustomCommand(
                command=f"/{skill.name}",
                prompt=prompt_with_companions,
                args=args,
                description=description,
            )
        )
    return commands


# Claude Code spec: $ARGUMENTS, $ARGUMENTS[N], $N.
# The ${...} forms of each are accepted too.
_INDEXED_ARG = re.compile(r"\$ARGUMENTS\[(\d+)\]|\$\{ARGUMENTS\[(\d+)\]\}")
_SHORTHAND_ARG = re.compile(r"\$(\d+)(?![a-zA-Z0-9_])")  # $N
_ALL_ARGS = re.compile(r"\$ARGUMENTS(?!\[)|\$\{ARGUMENTS\}")
_DEFAULTED_VAR = re.compile(r"\${([a-zA-Z0-9_]+):-[^}]+}")  # ${name:-default}
_BRACED_VAR = re.compile(r"\$\{([a-zA-Z0-9_]+)\}")  # ${name}
_BARE_VAR = re.compile(r"\$([a-zA-Z][a-zA-Z0-9_]*)")  # $name, never $N


def _extract_args(content: str) -> list[str]:
    """Every placeholder name `content` references, in first-appearance order.

    `ARGUMENTS` is excluded from the shell-style passes: it is spelled
    `arguments` by the `$ARGUMENTS` pass above them and would otherwise be
    collected twice under two different names.
    """
    names = [
        f"arg{indexed or braced}" for indexed, braced in _INDEXED_ARG.findall(content)
    ]
    names += [f"arg{n}" for n in _SHORTHAND_ARG.findall(content)]
    if _ALL_ARGS.search(content):
        names.append("arguments")
    names += _DEFAULTED_VAR.findall(content)
    names += [n for n in _BRACED_VAR.findall(content) if n != "ARGUMENTS"]
    names += [n for n in _BARE_VAR.findall(content) if n != "ARGUMENTS"]
    return list(dict.fromkeys(names))
