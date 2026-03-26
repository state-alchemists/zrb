from dataclasses import dataclass, field


@dataclass
class UIConfig:
    """Configuration for UI backends. See original Simple UI docs."""

    assistant_name: str = "Assistant"
    exit_commands: list[str] = field(default_factory=lambda: ["/exit", "/quit"])
    info_commands: list[str] = field(default_factory=lambda: ["/help", "/?"])
    save_commands: list[str] = field(default_factory=lambda: ["/save"])
    load_commands: list[str] = field(default_factory=lambda: ["/load"])
    attach_commands: list[str] = field(default_factory=lambda: ["/attach"])
    redirect_output_commands: list[str] = field(default_factory=lambda: ["/redirect"])
    yolo_toggle_commands: list[str] = field(default_factory=lambda: ["/yolo"])
    set_model_commands: list[str] = field(default_factory=lambda: ["/model"])
    exec_commands: list[str] = field(default_factory=lambda: ["/exec"])
    yolo: bool = False
    yolo_xcom_key: str = ""
    conversation_session_name: str = ""
    summarize_commands: list[str] = field(default_factory=lambda: ["/summarize"])

    @classmethod
    def default(cls) -> "UIConfig":
        return cls()

    @classmethod
    def minimal(cls) -> "UIConfig":
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
            yolo=self.yolo,
            yolo_xcom_key=self.yolo_xcom_key,
            conversation_session_name=self.conversation_session_name,
        )
