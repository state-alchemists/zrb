import os
import uuid
from collections.abc import Callable
from pathlib import Path

from zrb.config.config import CFG
from zrb.llm.hook.manager import hook_manager
from zrb.llm.skill.registry import SkillRegistry, skill_registry
from zrb.llm.skill.util import discover_companion_files
from zrb.util.asset_scanner import IGNORE_DIRS, scan_files
from zrb.util.dir_search import BUILTIN_PLUGIN_DIR, get_upward_dirs, scan_plugin_dirs
from zrb.util.frontmatter import parse_frontmatter
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
        """Define a skill programmatically, without a `SKILL.md` on disk.

        The filesystem loader builds these from frontmatter; construct one
        directly to register a skill from code:
        `skill_manager.add_skill(Skill(...))`.

        Args:
            name: Display name, and the `/slash-command` that invokes it.
            path: Directory the skill was loaded from. Resolves
                `companion_files` and any relative path in the content; pass the
                directory the skill should read relative to.
            description: What the skill is for. This is what the model matches
                on when deciding to activate it, so describe the *work*, not the
                topic.
            model_invocable: Whether the model may activate it on its own.
                False makes it user-invocable only.
            user_invocable: Whether it appears in the `/` menu.
            argument_hint: Placeholder shown in autocomplete, e.g. `"[filename]"`.
            allowed_tools: Tool names usable without permission while the skill
                is active, e.g. `["Read", "Grep"]`.
            model: Model override applied while the skill runs.
            context: Where it runs. `"fork"` runs it in a sub-agent instead of
                the current context.
            agent: Agent type to use when `context` forks, e.g. `"Explore"`.
            content: The skill body. Mutually exclusive with `content_factory`.
            content_factory: Callable returning the body, for content that must
                be built at activation time rather than at registration.
            companion_files: Paths, relative to `path`, that the skill's content
                refers to and that travel with it.
        """
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
    """Discover and resolve skills against a `SkillRegistry`.

    Decomposed per ADR-0090: the manager owns discovery (`scan`, `reload`,
    `get_search_directories`) and content resolution, and composes a
    `SkillRegistry` for the canonical collection. All query and mutation
    methods delegate to the registry, so a manual `add_skill`/`set_skills`
    survives a later scan (ADR-0090 Part 1).
    """

    def __init__(
        self,
        registry: SkillRegistry | None = None,
        root_dir: str = ".",
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 2,
        ignore_dirs: list[str] | None = None,
    ):
        """Create a skill manager over *registry*.

        Args:
            registry: The canonical `SkillRegistry` to read and write. A fresh
                registry is created when `None`, giving an isolated view.
            root_dir: Directory the project-level search starts from.
            search_dirs: Explicit directories to scan, replacing the defaults
                derived from `root_dir`.
            max_depth: How many directory levels below each search directory to
                descend.
            ignore_dirs: Directory names skipped while scanning.
        """
        self._registry = registry if registry is not None else SkillRegistry()
        self._root_dir = root_dir
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._ignore_dirs = IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        self._scanned = False

    @property
    def registry(self) -> SkillRegistry:
        """The canonical collection this manager reads and writes."""
        return self._registry

    def reload(self):
        """Force re-scan skills. Use after CFG changes or skill file updates.

        Manual registrations survive; only the discovered layer is refreshed.
        """
        self._scanned = False
        self._registry.clear_discovered()
        self._ensure_scanned()

    def scan(self, search_dirs: list[str | Path] | None = None) -> list[Skill]:
        """Discover skills on disk, replacing anything previously discovered.

        Manually-registered skills are kept; a manual registration wins a
        name collision with a discovered one.

        Args:
            search_dirs: Directories to scan. Defaults to those passed at
                construction, otherwise `get_search_directories()`.

        Returns:
            Every skill in the effective collection, in discovery order.
        """
        self._registry.clear_discovered()
        self._scan_results: dict[str, Skill] = {}
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
            self._scan_dir(Path(search_dir), max_depth=self._max_depth)
        self._registry.set_discovered(list(self._scan_results.values()))
        self._scanned = True
        return self.get_skills()

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
        Manually register a skill. Survives a later scan/reload.
        """
        self._registry.add_skill(skill)

    def remove_skill(self, name: str) -> None:
        """Drop a skill by name from the collection (manual and discovered)."""
        self._ensure_scanned()
        self._registry.remove_skill(name)

    def set_skills(self, skills):
        """Replace the whole collection with *skills*.

        *skills* may be a list of `Skill` or a deferred callable returning
        one. Like `add_skill`, this registration survives a later scan.
        """
        self._registry.set_skills(skills)

    def get_skills(self) -> list[Skill]:
        """Return all skills, scanning lazily on first call."""
        self._ensure_scanned()
        return self._registry.get_skills()

    def get_skill(self, name: str) -> Skill | None:
        """Look up one skill, scanning first if that has not happened yet.

        Matches the registry key, then falls back to matching a skill's own
        name or path. Returns None when nothing matches.
        """
        self._ensure_scanned()
        return self._registry.get_skill(name)

    def get_skill_content(self, name: str) -> str | None:
        """Return a skill's instruction text, or None if the skill is unknown.

        Resolves the name the same way `get_skill` does.
        """
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
        base = BUILTIN_PLUGIN_DIR
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
        if item.name == "SKILL.py" or item.name.endswith(".skill.py"):
            self._load_skill_from_python(full_path)
        elif item.name == "SKILL.md" or item.name.endswith(".skill.md"):
            self._load_skill_from_markdown(full_path)

    def _load_skill_from_python(self, full_path: str):
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
                self._scan_results[skill_obj.name] = skill_obj
            elif hasattr(module, "get_skill") and callable(module.get_skill):
                # Factory function that returns a Skill
                skill_obj = module.get_skill()
                if isinstance(skill_obj, Skill):
                    skill_obj.companion_files = discover_companion_files(full_path)
                    self._scan_results[skill_obj.name] = skill_obj

        except Exception as e:
            CFG.LOGGER.warning(f"Failed to load Python skill from {full_path}: {e}")

    def _load_skill_from_markdown(self, full_path: str):
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
                    frontmatter, _ = parse_frontmatter(content)
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

                    hooks_data = frontmatter.get("hooks")
                    if hooks_data:
                        if isinstance(hooks_data, dict):
                            hook_manager.parse_claude_format(
                                {"hooks": hooks_data}, full_path
                            )
                        elif isinstance(hooks_data, list):
                            # Zrb flat format
                            for hook_item in hooks_data:
                                hook_manager.parse_and_register(hook_item, full_path)

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
            self._scan_results[name] = Skill(
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


skill_manager = SkillManager(registry=skill_registry)
