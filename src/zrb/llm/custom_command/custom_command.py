import re

from zrb.llm.custom_command.any_custom_command import AnyCustomCommand


class CustomCommand(AnyCustomCommand):

    def __init__(
        self,
        command: str,
        prompt: str,
        args: list[str] | None = None,
        description: str | None = None,
    ):
        self._command = command
        self._prompt = prompt
        self._args = args if args is not None else []
        self._description = description

    @property
    def command(self) -> str:
        return self._command

    @property
    def description(self) -> str:
        if self._description:
            return self._description
        return f"{self.command} " + " ".join([f"<{a}>" for a in self.args])

    @property
    def args(self) -> list[str]:
        if len(self._args) == 0:
            return ["ARGUMENTS"]
        return self._args

    def get_prompt(self, kwargs: dict[str, str]) -> str:
        prompt = self._prompt
        # Prepare replacements
        replacements = dict(kwargs)
        for i, arg_name in enumerate(self.args):
            replacements[str(i + 1)] = kwargs.get(arg_name, "")
        replacements["ARGUMENTS"] = " ".join(kwargs.values())

        # 1. Replace ${name:-default}
        prompt = re.sub(
            r"\${([a-zA-Z0-9_]+):-([^}]+)}",
            lambda m: replacements.get(m.group(1), m.group(2)),
            prompt,
        )
        # 2. Replace ${name}
        prompt = re.sub(
            r"\${([a-zA-Z0-9_]+)}", lambda m: replacements.get(m.group(1), ""), prompt
        )
        # 3. Replace $name
        prompt = re.sub(
            r"\$([a-zA-Z0-9_]+)",
            lambda m: replacements.get(m.group(1), m.group(0)),
            prompt,
        )

        # If no replacement occurred and the original prompt has no placeholders,
        # append the arguments.
        if prompt == self._prompt and "$" not in self._prompt:
            args_info = (
                kwargs.get("ARGUMENTS", "")
                if len(self.args) == 1 and self.args[0] == "ARGUMENTS"
                else ", ".join([f"{k}: {v}" for k, v in kwargs.items()])
            )
            if args_info:
                prompt += f"\nARGUMENTS: {args_info}"
        return prompt
