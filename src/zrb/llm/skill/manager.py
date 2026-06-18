import os
import uuid
from collections.abc import Callable
from pathlib import Path

import yaml

from zrb.config.config import CFG
from zrb.llm.hook.manager import hook_manager
from zrb.llm.skill.util import discover_companion_files
from zrb.util.asset_scanner import IGNORE_DIRS, scan_files
from zrb.util.dir_search import get_upward_dirs, scan_plugin_dirs
from zrb.util.load import load_module_from_path


class Skill:
    """
    Represents a skill loaded from a SKILL.md or SKILL.py file.

    Skills can be invoked by users via /slash-commands or automatically by the model.

    Frontmatter fields (Claude Code spec):
        name: Display name (max 64 chars), becomes /slash-command
        description: Helps Claude decide when to use
        argument-hint: Shown in autocomplete (e.g., "[filename]")
        disable-model-invocation: Prevent auto-loading (true/false)
        user-invocable: Hide from / menu (true/false, default: true)
        allowed-tools: Tools usable without permission during skill (e.g., "Read, Grep")
        model: Model override for this skill
        context: Run in subagent (e.g., "fork")
        agent: Agent type for forked context (e.g., "Explore")
    """

    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        model_invocable: bool = True,
        user_invocable: bool = True,
        argument_hint: str | None = None,
        allowed_tools: list[str] | None = None,
        model: str | None = None,
        context: str | None = None,
        agent: str | None = None,
        content: str | None = None,
        content_factory: Callable[[], str] | None = None,
        companion_files: list[str] | None = None,
    ):
        self.name = name
        self.path = path
        self.description = description
        self.model_invocable = model_invocable
        self.user_invocable = user_invocable
        self.argument_hint = argument_hint
        self.allowed_tools = allowed_tools or []
        self.model = model
        self.context = context
        self.agent = agent
        self.content = content
        self.content_factory = content_factory
        self.companion_files = companion_files or []


class SkillManager:
    def __init__(
        self,
        root_dir: str = ".",
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 2,
        ignore_dirs: list[str] | None = None,
    ):
        self._root_dir = root_dir
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._skills: dict[str, Skill] = {}
        self._ignore_dirs = IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._scanned = False

    def reload(self):
        """Force re-scan skills. Use after CFG changes or skill file updates."""
        self._scanned = False
        self._skills = {}
        self._ensure_scanned()

    def scan(self, search_dirs: list[str | Path] | None = None) -> list[Skill]:
        self._skills = {}
        target_search_dirs = search_dirs
        if target_search_dirs is None:
            target_search_dirs = (
                self._search_dirs
                if self._search_dirs is not None
                else self.get_search_directories()
            )
        # Scan in order of precedence: global -> project
        # We iterate in normal order to allow later skills (project) to override earlier ones (global)
        for search_dir in target_search_dirs:
            self._scan_dir(search_dir, max_depth=self._max_depth)
        self._scanned = True
        return list(self._skills.values())

    _SKILL_ASSET = "skills"
    _PLUGIN_ASSET = "plugins"

    def get_search_directories(self) -> list[str | Path]:
        """Get all skill search directories in priority order.

        Priority (high → low):
        1. User home (~/.claude/, ~/.zrb/)
        2. Project traversal (filesystem root → cwd for each config dir name)
        3. Plugins from configured plugin dirs
        4. Base search directories
        5. Extra direct skill directories
        6. Builtin (always included, lowest priority)
        """
        search_dirs: list[str | Path] = []
        search_dirs.extend(self._get_home_search_dirs())
        search_dirs.extend(self._get_project_search_dirs())
        search_dirs.extend(self._get_plugin_search_dirs())
        search_dirs.extend(self._get_base_search_dirs())
        search_dirs.extend(self._get_extra_skill_dirs())
        search_dirs.extend(self._get_builtin_dirs())
        search_dirs.append(Path(self._root_dir))
        return search_dirs

    def add_skill(self, skill: Skill):
        """
        Manually register a skill.
        """
        self._skills[skill.name] = skill

    def get_skills(self) -> list[Skill]:
        """Return all scanned skills, scanning lazily on first call."""
        self._ensure_scanned()
        return list(self._skills.values())

    def get_skill(self, name: str) -> Skill | None:
        self._ensure_scanned()
        skill = self._skills.get(name)
        if not skill:
            # Try partial match or path match
            for s in self._skills.values():
                if s.name == name or s.path == name:
                    skill = s
                    break
        return skill

    def get_skill_content(self, name: str) -> str | None:
        self._ensure_scanned()
        skill = self.get_skill(name)
        if not skill:
            return None

        if skill.content:
            return skill.content

        if skill.content_factory:
            try:
                return skill.content_factory()
            except Exception as e:
                return f"Error executing skill factory: {e}"

        try:
            with open(skill.path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading skill file: {e}"

    def _ensure_scanned(self):
        """Auto-scan on first access if not already scanned."""
        if not self._scanned:
            self.scan()

    def _collect_skill_and_plugin_dirs(self, root: Path) -> list[Path]:
        """Collect ``skills/`` and plugin ``skills/`` directories under *root*."""
        dirs: list[Path] = []
        skill_path = root / self._SKILL_ASSET
        if skill_path.exists() and skill_path.is_dir():
            dirs.append(skill_path)
        plugins_dir = root / self._PLUGIN_ASSET
        if plugins_dir.exists() and plugins_dir.is_dir():
            for plugin_dir in scan_plugin_dirs(plugins_dir):
                skill_path = plugin_dir / self._SKILL_ASSET
                if skill_path.exists() and skill_path.is_dir():
                    dirs.append(skill_path)
        return dirs

    def _get_home_search_dirs(self) -> list[Path]:
        """User home directories — ~/.claude/, ~/.zrb/."""
        dirs: list[Path] = []
        if not CFG.LLM_SEARCH_HOME:
            return dirs
        home = Path.home()
        for pattern in CFG.LLM_CONFIG_DIR_NAMES:
            root = home / pattern
            if root.exists() and root.is_dir():
                dirs.extend(self._collect_skill_and_plugin_dirs(root))
        return dirs

    def _get_project_search_dirs(self) -> list[Path]:
        """Project directories — walk root → cwd looking for config dirs."""
        dirs: list[Path] = []
        if not CFG.LLM_SEARCH_PROJECT:
            return dirs
        for project_dir in self._get_upward_dirs():
            for pattern in CFG.LLM_CONFIG_DIR_NAMES:
                root = project_dir / pattern
                if root.exists() and root.is_dir():
                    dirs.extend(self._collect_skill_and_plugin_dirs(root))
        return dirs

    def _get_plugin_search_dirs(self) -> list[Path]:
        """Plugins from configured ``LLM_PLUGIN_DIRS``."""
        dirs: list[Path] = []
        for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
            plugin_path = Path(plugin_path_str)
            if plugin_path.exists() and plugin_path.is_dir():
                for plugin_dir in scan_plugin_dirs(plugin_path):
                    skill_path = plugin_dir / self._SKILL_ASSET
                    if skill_path.exists() and skill_path.is_dir():
                        dirs.append(skill_path)
        return dirs

    def _get_base_search_dirs(self) -> list[Path]:
        """Base search directories and their plugins."""
        dirs: list[Path] = []
        for root_str in CFG.LLM_BASE_SEARCH_DIRS:
            root = Path(root_str)
            if root.exists() and root.is_dir():
                dirs.extend(self._collect_skill_and_plugin_dirs(root))
        return dirs

    def _get_extra_skill_dirs(self) -> list[Path]:
        """Extra direct skill directories."""
        dirs: list[Path] = []
        for dir_str in CFG.LLM_EXTRA_SKILL_DIRS:
            dir_path = Path(dir_str)
            if dir_path.exists() and dir_path.is_dir():
                dirs.append(dir_path)
        return dirs

    def _get_builtin_dirs(self) -> list[Path]:
        """Builtin skill directories (always lowest priority).

        ``core_skills/`` is always included — core skills are the agent's
        methodology baseline that the utility skills delegate into, so they have
        no disable toggle. ``skills/`` (utility skills) is gated by
        ``CFG.LLM_ENABLE_BUILTIN_SKILLS``. Missing paths (broken install / unusual
        layout) are skipped rather than yielding a spurious default.
        """
        base = Path(__file__).parent.parent.parent / "llm_plugin"
        dirs: list[Path] = [base / "core_skills"]
        if CFG.LLM_ENABLE_BUILTIN_SKILLS:
            dirs.append(base / "skills")
        return [d for d in dirs if d.exists() and d.is_dir()]

    def _get_upward_dirs(self) -> list[Path]:
        """Get directories from root to cwd for upward traversal.
        Returns paths in root → cwd order.
        """
        return get_upward_dirs(self._root_dir)

    def _scan_dir(self, directory: Path, max_depth: int):
        try:
            scan_files(
                Path(directory),
                max_depth,
                self._on_file_found,
                self._ignore_dirs,
            )
        except Exception:
            CFG.LOGGER.warning(f"Failed to scan directory: {directory}", exc_info=True)

    def _on_file_found(self, item: Path) -> None:
        full_path = str(item)
        rel_path = os.path.relpath(full_path, self._root_dir)
        if item.name == "SKILL.py" or item.name.endswith(".skill.py"):
            self._load_skill_from_python(rel_path, full_path)
        elif item.name == "SKILL.md" or item.name.endswith(".skill.md"):
            self._load_skill_from_markdown(rel_path, full_path)

    def _load_skill_from_python(self, rel_path: str, full_path: str):
        try:
            module_name = f"zrb_skill_{uuid.uuid4().hex}"
            module = load_module_from_path(module_name, full_path)
            if not module:
                return

            skill_obj = None
            # Look for 'skill' or 'SKILL' variable
            if hasattr(module, "skill"):
                skill_obj = getattr(module, "skill")
            elif hasattr(module, "SKILL"):
                skill_obj = getattr(module, "SKILL")

            if isinstance(skill_obj, Skill):
                skill_obj.companion_files = discover_companion_files(full_path)
                self._skills[skill_obj.name] = skill_obj
            elif hasattr(module, "get_skill") and callable(module.get_skill):
                # Factory function that returns a Skill
                skill_obj = module.get_skill()
                if isinstance(skill_obj, Skill):
                    skill_obj.companion_files = discover_companion_files(full_path)
                    self._skills[skill_obj.name] = skill_obj

        except Exception as e:
            CFG.LOGGER.warning(f"Failed to load Python skill from {full_path}: {e}")

    def _load_skill_from_markdown(self, rel_path: str, full_path: str):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            default_name = os.path.basename(os.path.dirname(full_path))
            name = default_name
            description = "No description"
            model_invocable = True
            user_invocable = (
                True  # Default: skills are user-invocable (visible in / menu)
            )
            argument_hint = None
            allowed_tools: list[str] = []
            model = None
            context = None
            agent = None
            is_name_resolved = False

            # 1. Parse YAML Frontmatter
            if content.startswith("---"):
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        if frontmatter:
                            # Basic fields
                            if "name" in frontmatter:
                                name = frontmatter["name"]
                                is_name_resolved = True
                            description = frontmatter.get("description", description)
                            model_invocable = not frontmatter.get(
                                "disable-model-invocation", False
                            )
                            user_invocable = frontmatter.get("user-invocable", True)

                            # Claude Code spec fields
                            argument_hint = frontmatter.get("argument-hint")

                            # allowed-tools: comma-separated string or list
                            allowed_tools_raw = frontmatter.get("allowed-tools")
                            if allowed_tools_raw:
                                if isinstance(allowed_tools_raw, str):
                                    allowed_tools = [
                                        t.strip() for t in allowed_tools_raw.split(",")
                                    ]
                                elif isinstance(allowed_tools_raw, list):
                                    allowed_tools = allowed_tools_raw

                            model = frontmatter.get("model")
                            context = frontmatter.get("context")
                            agent = frontmatter.get("agent")

                            # Parse hooks if present
                            hooks_data = frontmatter.get("hooks")
                            if hooks_data:
                                if isinstance(hooks_data, dict):
                                    # Claude nested format
                                    hook_manager.parse_claude_format(
                                        {"hooks": hooks_data}, full_path
                                    )
                                elif isinstance(hooks_data, list):
                                    # Zrb flat format
                                    for hook_item in hooks_data:
                                        hook_manager.parse_and_register(
                                            hook_item, full_path
                                        )

                except Exception:
                    CFG.LOGGER.warning(
                        f"Failed to parse YAML frontmatter in {full_path}",
                        exc_info=True,
                    )

            # 2. Fallback: Parse Markdown for Header 1
            if not is_name_resolved:
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        name = stripped[2:].strip()
                        is_name_resolved = True
                        break

            # Use name as key, handle duplicates by overriding (precedence handled by scan order)
            self._skills[name] = Skill(
                name=name,
                path=full_path,
                description=description,
                model_invocable=model_invocable,
                user_invocable=user_invocable,
                argument_hint=argument_hint,
                allowed_tools=allowed_tools,
                model=model,
                context=context,
                agent=agent,
                content=content,  # Persist content to avoid re-reading
                companion_files=discover_companion_files(full_path),
            )
        except Exception as e:
            CFG.LOGGER.warning(f"Failed to load Markdown skill from {full_path}: {e}")


skill_manager = SkillManager()
