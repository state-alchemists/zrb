"""Filesystem traversal utilities for multi-tier configuration discovery.

Used by both the skill loader and hook loader to search in priority order:
user home → project directories (root→cwd) → plugins → extras → builtin.
"""

import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def get_upward_dirs(start_dir: str | Path) -> list[Path]:
    """Traverse from filesystem root to *start_dir*, returning paths in root → start_dir order.

    Useful for project-level configuration discovery (e.g., finding .claude/ or .zrb/
    directories anywhere between / and the current working directory).
    """
    try:
        cwd = Path(start_dir).resolve()
        # parents[0] is the immediate parent, parents[-1] is filesystem root
        return list(cwd.parents)[::-1] + [cwd]
    except Exception:
        # Path resolution failures are non-fatal — discovery just skips this root.
        # Expected: OSError (broken symlinks, permission) and RuntimeError (loops),
        # but stay broad so unusual filesystems can't take down discovery.
        _LOGGER.warning(
            "Failed to resolve upward directories from %s", start_dir, exc_info=True
        )
        return []


def scan_plugin_dirs(plugins_root: Path) -> list[Path]:
    """Scan *plugins_root* for plugin directories that carry a ``.claude-plugin/plugin.json`` manifest.

    Returns paths to valid plugin directories (manifest present), excluding hidden dirs.
    """
    plugin_dirs: list[Path] = []
    try:
        for item in plugins_root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                manifest = item / ".claude-plugin" / "plugin.json"
                if manifest.exists():
                    plugin_dirs.append(item)
    except Exception:
        # Discovery is best-effort. Expected: PermissionError/OSError on iterdir(),
        # but stay broad so a single bad plugin root can't take down the rest.
        _LOGGER.warning(
            "Failed to scan plugin directories: %s", plugins_root, exc_info=True
        )
    return plugin_dirs
