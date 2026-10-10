from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace

from zrb.config.config import CFG


def _commands(knob: str) -> Callable[[], list[str]]:
    """Default factory reading a `CFG.LLM_UI_COMMAND_*` knob at instantiation.

    Deferred because `zrb_init.py` may change the knob after import (R3).
    """
    return lambda: list(getattr(CFG, knob))


@dataclass
class UIConfig:
    """Configuration for UI backends.

    Every command-list field defaults from its `CFG.LLM_UI_COMMAND_*` twin.

    Example:
        config = UIConfig(
            assistant_name="MyBot",
            exit_commands=["/quit", "/bye"],
            is_yolo=False,
        )
        ui = MyUI(ui_config=config, llm_task=task, history_manager=hist)
    """

    assistant_name: str = field(default_factory=lambda: CFG.LLM_ASSISTANT_NAME)
    ascii_art: str = field(default_factory=lambda: CFG.LLM_ASSISTANT_ASCII_ART)
    jargon: str = field(default_factory=lambda: CFG.LLM_ASSISTANT_JARGON)
    greeting: str = field(
        default_factory=lambda: f"{CFG.LLM_ASSISTANT_NAME}\n{CFG.LLM_ASSISTANT_JARGON}"
    )

    # Commands (use empty list to disable)
    summarize_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_SUMMARIZE")
    )
    attach_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_ATTACH")
    )
    exit_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_EXIT"))
    info_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_INFO"))
    save_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_SAVE"))
    load_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_LOAD"))
    rewind_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_REWIND")
    )
    redirect_output_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_REDIRECT_OUTPUT")
    )
    yolo_toggle_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_YOLO_TOGGLE")
    )
    set_model_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_SET_MODEL")
    )
    set_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_SET"))
    exec_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_EXEC"))
    btw_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_BTW"))
    plan_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_PLAN_TOGGLE")
    )
    copy_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_COPY"))

    # Behavior
    is_yolo: bool | frozenset = (
        False  # True=full yolo, frozenset=selective yolo, False=off
    )
    # Stable so the task's xcom write and the UI agree on the key.
    yolo_xcom_key: str = "yolo"
    show_ollama_models: bool = field(default_factory=lambda: CFG.LLM_SHOW_OLLAMA_MODELS)
    show_pydantic_ai_models: bool = field(
        default_factory=lambda: CFG.LLM_SHOW_PYDANTIC_AI_MODELS
    )

    # Session
    conversation_session_name: str = ""  # Empty = random name

    @classmethod
    def default(cls) -> "UIConfig":
        """Get default configuration."""
        return cls()

    def merge_commands(self, ui_commands: dict) -> "UIConfig":
        """Copy this config with the named command lists replaced.

        Keys are the bare command names `LLMChatTask` stores them under
        (`"exit"`, `"set_model"`, ...); each maps to the `<key>_commands`
        field, except `"redirect"`. An unknown key is ignored so a stale
        alias does not break a session.
        """
        overrides = {}
        for key, value in ui_commands.items():
            name = _COMMAND_FIELD_ALIASES.get(key, f"{key}_commands")
            if name in _COMMAND_FIELDS:
                overrides[name] = value
        return replace(self, **overrides)


# Command keys whose field name is not `<key>_commands`.
_COMMAND_FIELD_ALIASES = {"redirect": "redirect_output_commands"}

# Guards `merge_commands` against writing a key that is not a command list.
_COMMAND_FIELDS = frozenset(
    f.name for f in fields(UIConfig) if f.name.endswith("_commands")
)

# Command-list fields whose `CFG.LLM_UI_COMMAND_*` name is not mechanical.
_COMMAND_FIELD_ENV_NAMES = {
    "redirect_output_commands": "LLM_UI_COMMAND_REDIRECT_OUTPUT",
    "plan_commands": "LLM_UI_COMMAND_PLAN_TOGGLE",
}


def command_env_name(field_name: str) -> str:
    """The `CFG.LLM_UI_COMMAND_*` setting that feeds `UIConfig.<field_name>`."""
    named = _COMMAND_FIELD_ENV_NAMES.get(field_name)
    if named is not None:
        return named
    return f"LLM_UI_COMMAND_{field_name[: -len('_commands')].upper()}"


def command_alias_field(env_name: str) -> str | None:
    """The `UIConfig` command-list field fed by `env_name`, or None.

    Lets `/set` re-point the running session's snapshot of that list.
    """
    for field_name in _COMMAND_FIELDS:
        if command_env_name(field_name) == env_name:
            return field_name
    return None


# `UIConfig` fields that mirror a plain `CFG` boolean.
_MODEL_VISIBILITY_FIELDS = {
    "LLM_SHOW_OLLAMA_MODELS": "show_ollama_models",
    "LLM_SHOW_PYDANTIC_AI_MODELS": "show_pydantic_ai_models",
}


def model_visibility_field(env_name: str) -> str | None:
    """The `UIConfig` field mirroring the `CFG.<env_name>` boolean, or None."""
    return _MODEL_VISIBILITY_FIELDS.get(env_name)
