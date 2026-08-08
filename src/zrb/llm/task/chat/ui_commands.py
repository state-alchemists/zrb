"""Slash-command aliases a chat session exposes.

`UICommands` is the user-facing override object; `UI_COMMAND_CFG_ATTRS` maps
each command to the `CFG` knob holding its default aliases. They live together
because they describe the same set of commands from two sides, and
`test_ui_commands.py` asserts they stay in step — adding a command means adding
one field and one entry.
"""

from dataclasses import dataclass, fields

# Command name -> the CFG attribute holding its default aliases.
UI_COMMAND_CFG_ATTRS: dict[str, str] = {
    "summarize": "LLM_UI_COMMAND_SUMMARIZE",
    "attach": "LLM_UI_COMMAND_ATTACH",
    "exit": "LLM_UI_COMMAND_EXIT",
    "info": "LLM_UI_COMMAND_INFO",
    "save": "LLM_UI_COMMAND_SAVE",
    "load": "LLM_UI_COMMAND_LOAD",
    "rewind": "LLM_UI_COMMAND_REWIND",
    "yolo_toggle": "LLM_UI_COMMAND_YOLO_TOGGLE",
    "set_model": "LLM_UI_COMMAND_SET_MODEL",
    "redirect_output": "LLM_UI_COMMAND_REDIRECT_OUTPUT",
    "exec": "LLM_UI_COMMAND_EXEC",
    "btw": "LLM_UI_COMMAND_BTW",
    "plan": "LLM_UI_COMMAND_PLAN_TOGGLE",
    "copy": "LLM_UI_COMMAND_COPY",
    "voice": "LLM_UI_COMMAND_VOICE",
}

Aliases = str | list[str] | None


@dataclass(frozen=True)
class UICommands:
    """Slash-command alias overrides for an `LLMChatTask`.

    Each field names one command and takes the alias (or aliases) that should
    invoke it. A field left as None keeps that command's configured default,
    resolved when the session starts — so a later environment change still
    wins.

    Pass a single string for one alias, or a list for several::

        LLMChatTask(
            name="chat",
            ui_commands=UICommands(exit="/quit", save=["/save", "/w"]),
        )

    Prefer this over a plain dict: the field names autocomplete, and a
    misspelled command is a `TypeError` at construction rather than an override
    that silently never applies.
    """

    summarize: Aliases = None
    attach: Aliases = None
    exit: Aliases = None
    info: Aliases = None
    save: Aliases = None
    load: Aliases = None
    rewind: Aliases = None
    yolo_toggle: Aliases = None
    set_model: Aliases = None
    redirect_output: Aliases = None
    exec: Aliases = None
    btw: Aliases = None
    plan: Aliases = None
    copy: Aliases = None
    voice: Aliases = None

    def to_overrides(self) -> dict[str, list[str]]:
        """Normalise the set fields into alias lists, keyed by command name.

        Fields left as None are omitted rather than emitted as empty lists, so
        the caller can tell "no override" from "override with nothing" and fall
        back to the configured default.
        """
        overrides: dict[str, list[str]] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            aliases = [value] if isinstance(value, str) else list(value)
            if aliases:
                overrides[field.name] = aliases
        return overrides
