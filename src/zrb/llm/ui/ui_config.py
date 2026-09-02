from dataclasses import dataclass, field
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
        ui = MyUI(config=config, llm_task=task, history_manager=hist)
    """

    # Identity
    assistant_name: str = field(default_factory=lambda: CFG.LLM_ASSISTANT_NAME)

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
        """Merge UI commands from task configuration.

        Args:
            ui_commands: Dictionary of commands from task configuration

        Returns:
            New UIConfig with merged commands
        """
        return UIConfig(
            exit_commands=ui_commands.get("exit", self.exit_commands),
            info_commands=ui_commands.get("info", self.info_commands),
            save_commands=ui_commands.get("save", self.save_commands),
            load_commands=ui_commands.get("load", self.load_commands),
            attach_commands=ui_commands.get("attach", self.attach_commands),
            photo_commands=ui_commands.get("photo", self.photo_commands),
            redirect_output_commands=ui_commands.get(
                "redirect", self.redirect_output_commands
            ),
            rewind_commands=ui_commands.get("rewind", self.rewind_commands),
            yolo_toggle_commands=ui_commands.get(
                "yolo_toggle", self.yolo_toggle_commands
            ),
            set_model_commands=ui_commands.get("set_model", self.set_model_commands),
            exec_commands=ui_commands.get("exec", self.exec_commands),
            btw_commands=ui_commands.get("btw", self.btw_commands),
            plan_commands=ui_commands.get("plan", self.plan_commands),
            copy_commands=ui_commands.get("copy", self.copy_commands),
            voice_commands=ui_commands.get("voice", self.voice_commands),
            summarize_commands=ui_commands.get("summarize", self.summarize_commands),
            assistant_name=self.assistant_name,
            is_yolo=self.is_yolo,
            yolo_xcom_key=self.yolo_xcom_key,
            conversation_session_name=self.conversation_session_name,
        )
