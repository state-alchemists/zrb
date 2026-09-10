from dataclasses import dataclass, field, fields, replace
from typing import Callable

from zrb.config.config import CFG


def _commands(knob: str) -> Callable[[], list[str]]:
    """Default factory reading a `CFG.LLM_UI_COMMAND_*` twin at instantiation.

    Deferred on purpose: `zrb_init.py` may change the knob after this module
    is imported (R3, ADR-0090 Part 3). `CFG`'s `EnvField` already parses the
    comma-separated env value into a list, so this just reads it — `list(...)`
    hands back a fresh copy rather than a reference into `CFG`'s own list.
    """
    return lambda: list(getattr(CFG, knob))


@dataclass
class UIConfig:
    """Configuration for UI backends.

    This dataclass replaces 25+ individual parameters in `BaseUI.__init__`.
    Every command-list field defaults from its `CFG.LLM_UI_COMMAND_*` twin
    (`src/zrb/config/mixins/llm_ui_commands.py`), so every UI backend agrees
    on the shipped command aliases without each one re-deriving them.

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
    exec_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_EXEC"))
    btw_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_BTW"))
    plan_commands: list[str] = field(
        default_factory=_commands("LLM_UI_COMMAND_PLAN_TOGGLE")
    )
    copy_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_COPY"))
    voice_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_VOICE"))
    photo_commands: list[str] = field(default_factory=_commands("LLM_UI_COMMAND_PHOTO"))

    # Behavior
    is_yolo: bool | frozenset = (
        False  # True=full yolo, frozenset=selective yolo, False=off
    )
    # A stable default (not per-instance) so a task's own xcom write of the
    # initial yolo state and a UI built from this same config agree on the
    # key without either having to see the other's resolved value.
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
        field, except `"redirect"`, whose field carries an `_output` infix.
        An unknown key is ignored rather than raising: the mapping is fed by
        task configuration, and a stale alias should not break a session.

        `replace` rather than a hand-written field list, so a field added to
        this dataclass is carried over automatically instead of being silently
        dropped until someone remembers to extend the list here.
        """
        overrides = {}
        for key, value in ui_commands.items():
            name = _COMMAND_FIELD_ALIASES.get(key, f"{key}_commands")
            if name in _COMMAND_FIELDS:
                overrides[name] = value
        return replace(self, **overrides)


# Command keys whose field name is not simply `<key>_commands`.
_COMMAND_FIELD_ALIASES = {"redirect": "redirect_output_commands"}

# Guards `merge_commands` against writing a key that is not a command list.
_COMMAND_FIELDS = frozenset(
    f.name for f in fields(UIConfig) if f.name.endswith("_commands")
)
