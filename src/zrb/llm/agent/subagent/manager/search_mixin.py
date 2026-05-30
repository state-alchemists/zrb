"""Search-directory discovery for ``SubAgentManager``.

Builds the priority-ordered list of directories to scan for sub-agents:
home → project traversal → plugins → base → extra → builtin → root_dir.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.util.dir_search import get_upward_dirs, scan_plugin_dirs


class SearchMixin:
    """Builds the search-directory list scanned by the loader mixin."""

    # Host-class contract: see ``LoaderMixin`` for the equivalent docs. ``_root_dir``
    # is owned by ``SubAgentManager.__init__``.
    if TYPE_CHECKING:
        _root_dir: str

    def get_search_directories(self) -> list[str | Path]:
        """All agent search directories in priority order (high → low).

        1. User home (``~/.claude/``, ``~/.zrb/``, …)
        2. Project traversal (filesystem root → cwd)
        3. Plugins from ``LLM_PLUGIN_DIRS``
        4. ``LLM_BASE_SEARCH_DIRS``
        5. ``LLM_EXTRA_AGENT_DIRS``
        6. Builtin (always included, lowest priority)
        7. ``self._root_dir`` (recursive scan target)
        """
        search_dirs: list[str | Path] = []
        home = Path.home()

        if CFG.LLM_SEARCH_HOME:
            for pattern in CFG.LLM_CONFIG_DIR_NAMES:
                self._add_agents_from_root(home / pattern, search_dirs)

        if CFG.LLM_SEARCH_PROJECT:
            for project_dir in get_upward_dirs(self._root_dir):
                for pattern in CFG.LLM_CONFIG_DIR_NAMES:
                    self._add_agents_from_root(project_dir / pattern, search_dirs)

        for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
            plugin_path = Path(plugin_path_str)
            if plugin_path.exists() and plugin_path.is_dir():
                for plugin_dir in scan_plugin_dirs(plugin_path):
                    agent_path = plugin_dir / "agents"
                    if agent_path.exists() and agent_path.is_dir():
                        search_dirs.append(agent_path)

        for root_str in CFG.LLM_BASE_SEARCH_DIRS:
            self._add_agents_from_root(Path(root_str), search_dirs)

        for dir_str in CFG.LLM_EXTRA_AGENT_DIRS:
            dir_path = Path(dir_str)
            if dir_path.exists() and dir_path.is_dir():
                search_dirs.append(dir_path)

        builtin_path = (
            Path(__file__).parent.parent.parent.parent.parent / "llm_plugin" / "agents"
        )
        if builtin_path.exists() and builtin_path.is_dir():
            search_dirs.append(builtin_path)

        search_dirs.append(Path(self._root_dir))
        return search_dirs

    def _add_agents_from_root(self, root: Path, search_dirs: list[str | Path]) -> None:
        """Append ``root/agents`` and any ``root/plugins/*/agents`` to *search_dirs*."""
        if not (root.exists() and root.is_dir()):
            return
        agent_path = root / "agents"
        if agent_path.exists() and agent_path.is_dir():
            search_dirs.append(agent_path)
        plugins_dir = root / "plugins"
        if plugins_dir.exists() and plugins_dir.is_dir():
            for plugin_dir in scan_plugin_dirs(plugins_dir):
                agent_path = plugin_dir / "agents"
                if agent_path.exists() and agent_path.is_dir():
                    search_dirs.append(agent_path)
