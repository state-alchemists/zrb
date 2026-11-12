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
MARKETPLACE_MANIFEST = Path(".claude-plugin") / "marketplace.json"
PLUGINS_DIR = "plugins"
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
    2. the plugins each checkout under ``marketplaces/`` publishes
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
    return _children_with_manifest(_subdirectories(plugins_root))


def _marketplace_dirs(plugins_root: Path) -> list[Path]:
    """The plugin directories every marketplace checkout publishes."""
    plugin_dirs: list[Path] = []
    for checkout in _subdirectories(plugins_root / MARKETPLACES_DIR):
        for plugin_dir in _checkout_plugin_dirs(checkout):
            if plugin_dir not in plugin_dirs:
                plugin_dirs.append(plugin_dir)
    return plugin_dirs


def _checkout_plugin_dirs(checkout: Path) -> list[Path]:
    """The plugin directories one marketplace checkout publishes.

    A marketplace almost always keeps its plugins in a ``plugins/`` folder, but
    the manifest is what actually says where each one is: ``source`` names the
    directory, relative to the checkout. That path is what a plugin is read
    from — a marketplace can publish skills from its own root, and an entry can
    point at a directory carrying no manifest of its own. The conventional
    ``plugins/*/`` children are added for a checkout whose manifest does not
    list them, and the root itself is kept last.

    Every candidate must resolve to a directory inside the checkout. A manifest
    is data that arrives with the checkout, not a grant: an absolute ``source``,
    a ``..`` that climbs out, or a symlink that leaves the checkout would let it
    make zrb import skills and agents from anywhere on the machine.
    """
    candidates = _declared_plugin_dirs(checkout)
    plugins_dir = checkout / PLUGINS_DIR
    if plugins_dir.is_dir():
        candidates.extend(_children_with_manifest(_subdirectories(plugins_dir)))
    candidates.append(checkout)
    return [path for path in candidates if _is_within(path, checkout)]


def _is_within(path: Path, root: Path) -> bool:
    """True when *path*, resolved, stays inside *root* — symlinks included."""
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        _LOGGER.warning("Ignoring a plugin source outside its marketplace: %s", path)
        return False
    return True


def _declared_plugin_dirs(checkout: Path) -> list[Path]:
    """The local ``source`` of every plugin a marketplace manifest lists."""
    manifest_path = checkout / MARKETPLACE_MANIFEST
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _LOGGER.warning(
            "Failed to read marketplace manifest: %s", manifest_path, exc_info=True
        )
        return []
    entries = manifest.get("plugins", []) if isinstance(manifest, dict) else []
    if not isinstance(entries, list):
        return []
    plugin_dirs: list[Path] = []
    for entry in entries:
        # A source that is not a path string lives somewhere else — a git repo,
        # an npm package — and is not on this disk to read. A path string that
        # names nothing is dropped the same way.
        source = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, str):
            continue
        plugin_dir = checkout / source
        if plugin_dir.is_dir() and plugin_dir not in plugin_dirs:
            plugin_dirs.append(plugin_dir)
    return plugin_dirs


def _children_with_manifest(directories: list[Path]) -> list[Path]:
    """The *directories* that carry a ``.claude-plugin/plugin.json``."""
    return [
        directory for directory in directories if (directory / PLUGIN_MANIFEST).exists()
    ]


def _subdirectories(directory: Path) -> list[Path]:
    """The immediate, non-hidden children of *directory*; empty when unreadable."""
    try:
        return [
            item
            for item in directory.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        ]
    except OSError:
        # Best-effort: one bad directory must not stop the rest.
        _LOGGER.warning("Failed to read directory: %s", directory, exc_info=True)
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
