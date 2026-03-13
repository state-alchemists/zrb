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
        # Build description with argument_hint if available
        description = skill.description
        if skill.argument_hint:
            description = f"{skill.description} {skill.argument_hint}"
        commands.append(
            CustomCommand(
                command=f"/{skill.name}",
                prompt=content,
                args=args,
                description=description,
            )
        )
    return commands


def _extract_args(content: str) -> list[str]:
    args = []
    # Claude Code spec: $ARGUMENTS, $ARGUMENTS[N], $N
    # Also support ${ARGUMENTS}, ${ARGUMENTS[N]}, ${N}

    # 1. $ARGUMENTS[N] or ${ARGUMENTS[N]} (indexed arguments)
    matches = re.findall(r"\$ARGUMENTS\[(\d+)\]|\$\{ARGUMENTS\[(\d+)\]\}", content)
    for match in matches:
        arg = match[0] or match[1]
        if arg not in args:
            args.append(f"arg{arg}")

    # 2. $N (shorthand for $ARGUMENTS[N])
    matches = re.findall(r"\$(\d+)(?![a-zA-Z0-9_])", content)
    for match in matches:
        arg_name = f"arg{match}"
        if arg_name not in args:
            args.append(arg_name)

    # 3. $ARGUMENTS or ${ARGUMENTS} (all arguments)
    if re.search(r"\$ARGUMENTS(?!\[)|\$\{ARGUMENTS\}", content):
        if "arguments" not in args:
            args.append("arguments")

    # 4. Legacy: ${name:-default}
    matches = re.findall(r"\${([a-zA-Z0-9_]+):-[^}]+}", content)
    for match in matches:
        if match not in args:
            args.append(match)

    # 5. Legacy: ${name}
    # Avoid re-adding ARGUMENTS
    matches = re.findall(r"\$\{([a-zA-Z0-9_]+)\}", content)
    for match in matches:
        if match not in args and match != "ARGUMENTS":
            args.append(match)

    # 6. Legacy: $name (but not $N which is shorthand)
    # Avoid re-adding ARGUMENTS, numbers, or special vars
    matches = re.findall(r"\$([a-zA-Z][a-zA-Z0-9_]*)", content)
    special_vars = {"ARGUMENTS"}
    for match in matches:
        if match not in args and match not in special_vars:
            args.append(match)

    # Remove duplicates while preserving order
    unique_args = []
    for arg in args:
        if arg not in unique_args:
            unique_args.append(arg)

    return unique_args
