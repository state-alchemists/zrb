import logging
from pathlib import Path

from zrb.config.config import CFG
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator

logger = logging.getLogger(__name__)


def get_search_directories() -> list[str | Path]:
    search_dirs: list[str | Path] = []
    zrb_dir_name = f".{CFG.ROOT_GROUP_NAME}"

    # 0. Plugins (Default Plugin -> User Plugins)
    # Default Plugin
    default_plugin_path = Path(__file__).parent.parent.parent / "llm_plugin"
    if default_plugin_path.exists() and default_plugin_path.is_dir():
        hooks_path = default_plugin_path / "hooks"
        if hooks_path.exists() and hooks_path.is_dir():
            search_dirs.append(hooks_path)
        hooks_file = default_plugin_path / "hooks.json"
        if hooks_file.exists() and hooks_file.is_file():
            search_dirs.append(hooks_file)

    # User Plugins
    for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
        plugin_path = Path(plugin_path_str)
        if plugin_path.exists() and plugin_path.is_dir():
            hooks_path = plugin_path / "hooks"
            if hooks_path.exists() and hooks_path.is_dir():
                search_dirs.append(hooks_path)
            hooks_file = plugin_path / "hooks.json"
            if hooks_file.exists() and hooks_file.is_file():
                search_dirs.append(hooks_file)

    # 1. User global config (~/.zrb/hooks.json and ~/.zrb/hooks/)
    try:
        home = Path.home()
        # Claude style
        global_claude_hooks_file = home / ".claude" / "hooks.json"
        if global_claude_hooks_file.exists() and global_claude_hooks_file.is_file():
            search_dirs.append(global_claude_hooks_file)

        global_claude_hooks_dir = home / ".claude" / "hooks"
        if global_claude_hooks_dir.exists() and global_claude_hooks_dir.is_dir():
            search_dirs.append(global_claude_hooks_dir)

        # Zrb style
        global_zrb_hooks_file = home / zrb_dir_name / "hooks.json"
        if global_zrb_hooks_file.exists() and global_zrb_hooks_file.is_file():
            search_dirs.append(global_zrb_hooks_file)

        global_zrb_hooks_dir = home / zrb_dir_name / "hooks"
        if global_zrb_hooks_dir.exists() and global_zrb_hooks_dir.is_dir():
            search_dirs.append(global_zrb_hooks_dir)
    except Exception:
        pass

    # 2. Project directories (.zrb/hooks.json and .zrb/hooks/)
    try:
        cwd = Path.cwd()
        project_dirs = list(cwd.parents)[::-1] + [cwd]
        for project_dir in project_dirs:
            # Claude style
            local_claude_hooks_file = project_dir / ".claude" / "hooks.json"
            if (
                local_claude_hooks_file.exists()
                and local_claude_hooks_file.is_file()
            ):
                search_dirs.append(local_claude_hooks_file)

            local_claude_hooks_dir = project_dir / ".claude" / "hooks"
            if local_claude_hooks_dir.exists() and local_claude_hooks_dir.is_dir():
                search_dirs.append(local_claude_hooks_dir)

            # Zrb style
            local_zrb_hooks_file = project_dir / zrb_dir_name / "hooks.json"
            if local_zrb_hooks_file.exists() and local_zrb_hooks_file.is_file():
                search_dirs.append(local_zrb_hooks_file)

            local_zrb_hooks_dir = project_dir / zrb_dir_name / "hooks"
            if local_zrb_hooks_dir.exists() and local_zrb_hooks_dir.is_dir():
                search_dirs.append(local_zrb_hooks_dir)
    except Exception:
        pass

    # 3. Custom directories from CFG
    for d in CFG.HOOKS_DIRS:
        search_dirs.append(Path(d))

    return search_dirs


def parse_hook_config(data: dict) -> HookConfig:
    # Manual parsing because we are not using Pydantic BaseModel
    name = data["name"]
    events = [HookEvent(e) for e in data["events"]]
    hook_type = HookType(data["type"])

    raw_config = data["config"]
    default_timeout = 30
    if hook_type == HookType.COMMAND:
        config = CommandHookConfig(
            command=raw_config["command"],
            shell=raw_config.get("shell", True),
            working_dir=raw_config.get("working_dir"),
        )
        default_timeout = 600
    elif hook_type == HookType.PROMPT:
        config = PromptHookConfig(
            user_prompt_template=raw_config["user_prompt_template"],
            system_prompt=raw_config.get("system_prompt"),
            model=raw_config.get("model"),
            temperature=raw_config.get("temperature", 0.0),
        )
        default_timeout = 30
    elif hook_type == HookType.AGENT:
        config = AgentHookConfig(
            system_prompt=raw_config["system_prompt"],
            tools=raw_config.get("tools"),
            model=raw_config.get("model"),
        )
        default_timeout = 60
    else:
        raise ValueError(f"Unknown hook type: {hook_type}")

    matchers = []
    for m in data.get("matchers", []):
        matchers.append(
            MatcherConfig(
                field=m["field"],
                operator=MatcherOperator(m["operator"]),
                value=m["value"],
                case_sensitive=m.get("case_sensitive", True),
            )
        )

    return HookConfig(
        name=name,
        events=events,
        type=hook_type,
        config=config,
        description=data.get("description"),
        matchers=matchers,
        is_async=data.get("async", False),
        enabled=data.get("enabled", True),
        timeout=data.get("timeout", default_timeout),
        env=data.get("env"),
        priority=data.get("priority", 0),
    )
