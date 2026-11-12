"""Filesystem traversal utilities for multi-tier configuration discovery.

Used by both the skill loader and hook loader to search in priority order:
user home → project directories (root→cwd) → plugins → extras → builtin.
"""

import json
import logging
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# The shipped `zrb/llm_plugin/` tree, found by walking up to the `zrb` package.
BUILTIN_PLUGIN_DIR = (
    next(p for p in Path(__file__).resolve().parents if p.name == "zrb") / "llm_plugin"
)

# A plugins root is not a flat list of plugins. A plugin can be checked out in
# place, or unpacked under `cache/` by a marketplace install — in which case
# `installed_plugins.json` is what records where it actually lives.
PLUGIN_MANIFEST = Path(".claude-plugin") / "plugin.json"
INSTALLED_PLUGINS_INDEX = "installed_plugins.json"
MARKETPLACES_DIR = "marketplaces"


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
        # Best-effort: skip a root that cannot be resolved.
        _LOGGER.warning(
            "Failed to resolve upward directories from %s", start_dir, exc_info=True
        )
        return []


def get_dirs_up_to_home(start_dir: str, home_dir: str) -> list[str]:
    """*start_dir* followed by each ancestor up to *home_dir*, nearest first.

    Only *start_dir* when it is not under *home_dir* (or on another drive).
    """
    dirs = [start_dir]
    try:
        if os.path.commonpath([start_dir, home_dir]) != home_dir:
            return dirs
    except ValueError:
        return dirs
    current = start_dir
    while current != home_dir:
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
        dirs.append(current)
    return dirs


def scan_plugin_dirs(plugins_root: Path) -> list[Path]:
    """Every plugin directory under *plugins_root*, from all of Claude Code's layouts.

    Three sources are read, in the order a caller should let them lose a name
    collision — a marketplace checkout before the installed copy of the same
    plugin, so the version Claude Code actually loads wins:

    1. an immediate child carrying ``.claude-plugin/plugin.json``
    2. every marketplace checkout under ``marketplaces/``
    3. the ``installPath`` of every plugin ``installed_plugins.json`` records

    Hidden entries, missing sources and an unreadable index contribute nothing
    rather than raising.
    """
    plugin_dirs: list[Path] = []
    for source in (_direct_plugin_dirs, _marketplace_dirs, _installed_plugin_dirs):
        for plugin_dir in source(plugins_root):
            if plugin_dir not in plugin_dirs:
                plugin_dirs.append(plugin_dir)
    return plugin_dirs


def _direct_plugin_dirs(plugins_root: Path) -> list[Path]:
    """Immediate children that carry a plugin manifest of their own."""
    try:
        return [
            item
            for item in plugins_root.iterdir()
            if item.is_dir()
            and not item.name.startswith(".")
            and (item / PLUGIN_MANIFEST).exists()
        ]
    except OSError:
        # Best-effort: a bad plugin root must not stop the rest.
        _LOGGER.warning(
            "Failed to scan plugin directories: %s", plugins_root, exc_info=True
        )
        return []


def _marketplace_dirs(plugins_root: Path) -> list[Path]:
    """Marketplace checkouts, each of which carries the skills it publishes."""
    marketplaces_root = plugins_root / MARKETPLACES_DIR
    if not marketplaces_root.is_dir():
        return []
    try:
        return [
            item
            for item in marketplaces_root.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        ]
    except OSError:
        _LOGGER.warning(
            "Failed to scan marketplaces: %s", marketplaces_root, exc_info=True
        )
        return []


def _installed_plugin_dirs(plugins_root: Path) -> list[Path]:
    """The ``installPath`` of every plugin ``installed_plugins.json`` records."""
    index_path = plugins_root / INSTALLED_PLUGINS_INDEX
    if not index_path.is_file():
        return []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _LOGGER.warning("Failed to read plugin index: %s", index_path, exc_info=True)
        return []
    plugins = index.get("plugins", {}) if isinstance(index, dict) else {}
    if not isinstance(plugins, dict):
        return []
    plugin_dirs: list[Path] = []
    for entries in plugins.values():
        # v2 indexes a list of scoped entries; accept a bare entry too.
        for entry in entries if isinstance(entries, list) else [entries]:
            install_path = entry.get("installPath") if isinstance(entry, dict) else None
            if not isinstance(install_path, str):
                continue
            plugin_dir = Path(install_path).expanduser()
            if plugin_dir.is_dir() and plugin_dir not in plugin_dirs:
                plugin_dirs.append(plugin_dir)
    return plugin_dirs
