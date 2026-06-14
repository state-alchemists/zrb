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
from zrb.util.dir_search import get_upward_dirs

logger = logging.getLogger(__name__)


def _zrb_dir_name() -> str:
    """Return the Zrb config directory name (evaluated lazily to avoid CFG init ordering issues)."""
    return f".{CFG.ROOT_GROUP_NAME}"


def get_search_directories() -> list[str | Path]:
    """Get all hook search directories/files in priority order.

    Priority (high → low):
    0. Default plugin (llm_plugin) + user plugins
    1. User global config (~/.claude/, ~/.zrb/)
    2. Project directories (root → cwd)
    3. Custom directories from CFG.HOOKS_DIRS
    """
    dirs: list[str | Path] = []
    dirs.extend(_get_plugin_hook_dirs())
    dirs.extend(_get_home_hook_dirs())
    dirs.extend(_get_project_hook_dirs())
    dirs.extend(_get_custom_hook_dirs())
    return _dedup_paths(dirs)


def _dedup_paths(paths: list[str | Path]) -> list[str | Path]:
    """Drop duplicate paths, keeping the first (highest-precedence) occurrence.

    ``$HOME`` is searched by both the home tier and the project upward-walk
    whenever cwd is under ``$HOME``, so without this every ``~/.claude`` hook
    would be discovered — and registered, and fired — twice. Dedup by resolved
    path so symlinked aliases collapse too.
    """
    seen: set[str] = set()
    unique: list[str | Path] = []
    for path in paths:
        try:
            key = str(Path(path).resolve())
        except Exception:
            # Unresolvable path (broken symlink, permission): fall back to the
            # literal string so it still dedups against an identical literal.
            key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _collect_hook_paths(base_dir: Path) -> list[str | Path]:
    """Collect ``hooks.json`` and ``hooks/`` under *base_dir* for both Claude and Zrb styles."""
    paths: list[str | Path] = []

    claude_file = base_dir / ".claude" / "hooks.json"
    if claude_file.exists() and claude_file.is_file():
        paths.append(claude_file)

    claude_dir = base_dir / ".claude" / "hooks"
    if claude_dir.exists() and claude_dir.is_dir():
        paths.append(claude_dir)

    # Claude Code registers hooks inside settings.json / settings.local.json
    # under a nested "hooks" block — NOT in hooks.json. Drop-in tools like
    # peon-ping install themselves there, so we read those files too. The
    # nested block is parsed by HookLoaderMixin._parse_claude_format; any other
    # settings keys (model, env, permissions, …) are ignored.
    for settings_name in ("settings.json", "settings.local.json"):
        settings_file = base_dir / ".claude" / settings_name
        if settings_file.exists() and settings_file.is_file():
            paths.append(settings_file)

    zrb_file = base_dir / _zrb_dir_name() / "hooks.json"
    if zrb_file.exists() and zrb_file.is_file():
        paths.append(zrb_file)

    zrb_dir = base_dir / _zrb_dir_name() / "hooks"
    if zrb_dir.exists() and zrb_dir.is_dir():
        paths.append(zrb_dir)

    return paths


def _get_plugin_hook_dirs() -> list[str | Path]:
    """Default plugin (llm_plugin) and user plugin hook directories."""
    paths: list[str | Path] = []

    # Default Plugin
    default_plugin_path = Path(__file__).parent.parent.parent / "llm_plugin"
    if default_plugin_path.exists() and default_plugin_path.is_dir():
        hooks_path = default_plugin_path / "hooks"
        if hooks_path.exists() and hooks_path.is_dir():
            paths.append(hooks_path)
        hooks_file = default_plugin_path / "hooks.json"
        if hooks_file.exists() and hooks_file.is_file():
            paths.append(hooks_file)

    # User Plugins
    for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
        plugin_path = Path(plugin_path_str)
        if plugin_path.exists() and plugin_path.is_dir():
            hooks_path = plugin_path / "hooks"
            if hooks_path.exists() and hooks_path.is_dir():
                paths.append(hooks_path)
            hooks_file = plugin_path / "hooks.json"
            if hooks_file.exists() and hooks_file.is_file():
                paths.append(hooks_file)

    return paths


def _get_home_hook_dirs() -> list[str | Path]:
    """User global config — ~/.claude/ and ~/.zrb/."""
    try:
        return _collect_hook_paths(Path.home())
    except Exception:
        # Hook discovery must never abort startup. PermissionError/OSError on path
        # ops and RuntimeError from Path.home() (HOME unset) are the expected cases,
        # but we swallow everything to stay resilient to unusual filesystems.
        logger.warning("Failed to search global hook directories", exc_info=True)
        return []


def _get_project_hook_dirs() -> list[str | Path]:
    """Project directories — walk root → cwd looking for hook configs."""
    try:
        paths: list[str | Path] = []
        for project_dir in get_upward_dirs(Path.cwd()):
            paths.extend(_collect_hook_paths(project_dir))
        return paths
    except Exception:
        # Same rationale as _get_home_hook_dirs: never let project discovery
        # abort startup on unexpected filesystem state.
        logger.warning("Failed to search project hook directories", exc_info=True)
        return []


def _get_custom_hook_dirs() -> list[str | Path]:
    """Custom directories from ``CFG.HOOKS_DIRS``."""
    return [Path(d) for d in CFG.HOOKS_DIRS]


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
