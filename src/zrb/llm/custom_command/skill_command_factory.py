import re
from collections.abc import Callable

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.custom_command.custom_command import CustomCommand
from zrb.llm.skill.activation import build_activation_block
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.llm.skill.preload import format_preload_problems, resolve_preload


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
        prompt_with_companions = _build_prompt(skill_manager, skill, content)
        commands.append(
            CustomCommand(
                command=f"/{skill.name}",
                prompt=prompt_with_companions,
                args=args,
                description=description,
            )
        )
    return commands


def _build_prompt(skill_manager: SkillManager, skill: Skill, content: str) -> str:
    """The skill body with any `preload:` dependencies ahead of it."""
    preloaded, problems = resolve_preload(skill_manager, skill)
    blocks = [
        build_activation_block(
            dependency,
            skill_manager.get_skill_content(dependency.name) or dependency.description,
            preloaded_by=skill.name,
        )
        for dependency in preloaded
    ]
    blocks.append(build_activation_block(skill, content))
    if problems:
        blocks.append(format_preload_problems(problems))
    return "\n\n".join(blocks)


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
