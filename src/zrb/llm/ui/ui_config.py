from dataclasses import dataclass, field


@dataclass
class UIConfig:
    """Configuration for UI backends.

    This dataclass replaces 25+ individual parameters in BaseUI.__init__.
    Use this for cleaner, more maintainable UI implementations.

    Example:
        config = UIConfig(
            assistant_name="MyBot",
            exit_commands=["/quit", "/bye"],
            is_yolo=False,
        )
        ui = MyUI(config=config, llm_task=task, history_manager=hist)
    """

    # Identity
    assistant_name: str = "Assistant"

    # Commands (use empty list to disable)
    exit_commands: list[str] = field(default_factory=lambda: ["/exit", "/quit"])
    info_commands: list[str] = field(default_factory=lambda: ["/help", "/?"])
    save_commands: list[str] = field(default_factory=lambda: ["/save"])
    load_commands: list[str] = field(default_factory=lambda: ["/load"])
    attach_commands: list[str] = field(default_factory=lambda: ["/attach"])
    redirect_output_commands: list[str] = field(default_factory=lambda: ["/redirect"])
    yolo_toggle_commands: list[str] = field(default_factory=lambda: ["/yolo"])
    set_model_commands: list[str] = field(default_factory=lambda: ["/model"])
    exec_commands: list[str] = field(default_factory=lambda: ["/exec"])

    # Behavior
    is_yolo: bool | frozenset = (
        False  # True=full yolo, frozenset=selective yolo, False=off
    )
    yolo_xcom_key: str = ""  # Empty = auto-generate

    # Session
    conversation_session_name: str = ""  # Empty = random name

    @classmethod
    def default(cls) -> "UIConfig":
        """Get default configuration."""
        return cls()

    @classmethod
    def minimal(cls) -> "UIConfig":
        """Minimal config - disables most commands."""
        return cls(
            exit_commands=["/exit"],
            info_commands=[],
            save_commands=[],
            load_commands=[],
            attach_commands=[],
            redirect_output_commands=[],
            yolo_toggle_commands=[],
            set_model_commands=[],
            exec_commands=[],
        )

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
            redirect_output_commands=ui_commands.get(
                "redirect", self.redirect_output_commands
            ),
            yolo_toggle_commands=ui_commands.get(
                "yolo_toggle", self.yolo_toggle_commands
            ),
            set_model_commands=ui_commands.get("set_model", self.set_model_commands),
            exec_commands=ui_commands.get("exec", self.exec_commands),
            summarize_commands=self.summarize_commands,
            assistant_name=self.assistant_name,
            is_yolo=self.is_yolo,
            yolo_xcom_key=self.yolo_xcom_key,
            conversation_session_name=self.conversation_session_name,
        )

    # For compatibility with merge_commands
    summarize_commands: list[str] = field(default_factory=lambda: ["/summarize"])
