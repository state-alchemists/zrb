"""Search-directory discovery for ``SubAgentManager``.

Builds the priority-ordered list of directories to scan for sub-agents:
home → project traversal → plugins → base → extra → core builtin → optional builtin → root_dir.
"""

from __future__ import annotations

from pathlib import Path

from zrb.config.config import CFG
from zrb.util.dir_search import BUILTIN_PLUGIN_DIR, get_upward_dirs, scan_plugin_dirs


class SubAgentManagerSearch:
    """Builds the search-directory list scanned by the loading collaborator.

    Stateless: `root_dir` is owned by `SubAgentManager` and passed in per call
    rather than cached here, since it can change after construction (e.g. a
    test retargeting `manager.root_dir`).
    """

    def get_search_directories(self, root_dir: str) -> list[str | Path]:
        """All agent search directories in priority order (high → low).

        1. User home (``~/.claude/``, ``~/.zrb/``, …)
        2. Project traversal (filesystem root → cwd)
        3. Plugins from ``LLM_PLUGIN_DIRS``
        4. ``LLM_BASE_SEARCH_DIRS``
        5. ``LLM_EXTRA_AGENT_DIRS``
        6. Core builtin agents (always included, lowest priority)
        7. Optional builtin agents (gated by ``LLM_ENABLE_BUILTIN_AGENTS``)
        8. ``root_dir`` (recursive scan target)
        """
        search_dirs: list[str | Path] = []
        home = Path.home()

        if CFG.LLM_SEARCH_HOME:
            for pattern in CFG.LLM_CONFIG_DIR_NAMES:
                self._add_agents_from_root(home / pattern, search_dirs)

        if CFG.LLM_SEARCH_PROJECT:
            for project_dir in get_upward_dirs(root_dir):
                for pattern in CFG.LLM_CONFIG_DIR_NAMES:
                    self._add_agents_from_root(project_dir / pattern, search_dirs)

        for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
            plugin_path = Path(plugin_path_str)
            if plugin_path.exists() and plugin_path.is_dir():
                for plugin_dir in scan_plugin_dirs(plugin_path):
                    _append_if_dir(plugin_dir / "agents", search_dirs)

        for root_str in CFG.LLM_BASE_SEARCH_DIRS:
            self._add_agents_from_root(Path(root_str), search_dirs)

        for dir_str in CFG.LLM_EXTRA_AGENT_DIRS:
            _append_if_dir(Path(dir_str), search_dirs)

        _append_if_dir(BUILTIN_PLUGIN_DIR / "core_agents", search_dirs)

        if CFG.LLM_ENABLE_BUILTIN_AGENTS:
            _append_if_dir(BUILTIN_PLUGIN_DIR / "agents", search_dirs)

        search_dirs.append(Path(root_dir))
        return search_dirs

    def _add_agents_from_root(self, root: Path, search_dirs: list[str | Path]) -> None:
        """Append ``root/agents`` and any ``root/plugins/*/agents`` to *search_dirs*."""
        if not (root.exists() and root.is_dir()):
            return
        _append_if_dir(root / "agents", search_dirs)
        plugins_dir = root / "plugins"
        if plugins_dir.exists() and plugins_dir.is_dir():
            for plugin_dir in scan_plugin_dirs(plugins_dir):
                _append_if_dir(plugin_dir / "agents", search_dirs)


def _append_if_dir(path: Path, search_dirs: list[str | Path]) -> None:
    """Append *path* to *search_dirs* if it exists and is a directory."""
    if path.exists() and path.is_dir():
        search_dirs.append(path)
