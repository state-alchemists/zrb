import re
from collections.abc import Callable

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.custom_command.custom_command import CustomCommand
from zrb.llm.skill.manager import SkillManager


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
        commands.append(
            CustomCommand(
                command=f"/{skill.name}",
                prompt=content,
                args=args,
                description=skill.description,
            )
        )
    return commands


def _extract_args(content: str) -> list[str]:
    args = []
    # 1. Replace ${name:-default}
    matches = re.findall(r"\${([a-zA-Z0-9_]+):-[^}]+}", content)
    args.extend(matches)

    # 2. Replace ${name}
    matches = re.findall(r"\${([a-zA-Z0-9_]+)}", content)
    args.extend(matches)

    # 3. Replace $name
    matches = re.findall(r"\$([a-zA-Z0-9_]+)", content)
    args.extend(matches)

    # Remove duplicates while preserving order
    unique_args = []
    for arg in args:
        if arg not in unique_args:
            unique_args.append(arg)

    return unique_args
