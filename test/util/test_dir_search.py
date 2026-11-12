"""Tests for util/dir_search.py — covers happy paths and exception fallbacks."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from zrb.util.dir_search import (
    get_dirs_up_to_home,
    get_upward_dirs,
    scan_plugin_dirs,
    split_config_dir_patterns,
)


def test_get_upward_dirs_returns_root_to_start(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    result = get_upward_dirs(nested)
    # Result is root → start_dir; last element must be the resolved start_dir
    assert result[-1] == nested.resolve()
    # Parents appear in increasing depth
    assert nested.resolve().parent in result


def test_get_upward_dirs_falls_back_on_exception(caplog):
    with patch(
        "zrb.util.dir_search.Path.resolve",
        side_effect=OSError("bad symlink"),
    ):
        result = get_upward_dirs("/some/path")
    assert result == []


def test_scan_plugin_dirs_collects_valid_manifests(tmp_path):
    plugin_a = tmp_path / "plugin_a" / ".claude-plugin"
    plugin_a.mkdir(parents=True)
    (plugin_a / "plugin.json").write_text("{}")

    plugin_b = tmp_path / "plugin_b"
    plugin_b.mkdir()  # no manifest

    hidden = tmp_path / ".hidden"
    hidden.mkdir()  # excluded by leading dot

    result = scan_plugin_dirs(tmp_path)
    assert tmp_path / "plugin_a" in result
    assert tmp_path / "plugin_b" not in result
    assert hidden not in result


def test_scan_plugin_dirs_returns_empty_on_error():
    bogus = Path("/no/such/dir/anywhere/123")
    # iterdir() on a nonexistent dir raises FileNotFoundError; helper must swallow.
    assert scan_plugin_dirs(bogus) == []


def _write_plugin_index(plugins_root: Path, plugins: dict) -> None:
    plugins_root.mkdir(parents=True, exist_ok=True)
    (plugins_root / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8"
    )


def test_scan_plugin_dirs_follows_installed_plugin_index(tmp_path):
    installed = tmp_path / "cache" / "market" / "documents" / "abc123"
    (installed / "skills" / "pdf").mkdir(parents=True)
    _write_plugin_index(
        tmp_path,
        {"documents@market": [{"scope": "user", "installPath": str(installed)}]},
    )
    assert installed in scan_plugin_dirs(tmp_path)


def test_scan_plugin_dirs_accepts_a_bare_entry(tmp_path):
    "A plugin indexed as one entry rather than a list of scoped entries."
    installed = tmp_path / "cache" / "documents"
    installed.mkdir(parents=True)
    _write_plugin_index(tmp_path, {"documents@market": {"installPath": str(installed)}})
    assert installed in scan_plugin_dirs(tmp_path)


def test_scan_plugin_dirs_lists_marketplace_checkouts(tmp_path):
    checkout = tmp_path / "marketplaces" / "anthropic-skills"
    (checkout / "skills" / "pdf").mkdir(parents=True)
    assert checkout in scan_plugin_dirs(tmp_path)


def test_scan_plugin_dirs_reads_a_marketplaces_plugins_folder(tmp_path):
    "A marketplace keeps its plugins in `plugins/<name>/` — the documented layout."
    plugin = tmp_path / "marketplaces" / "acme" / "plugins" / "documents"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (plugin / "skills" / "pdf").mkdir(parents=True)
    assert plugin in scan_plugin_dirs(tmp_path)


def test_scan_plugin_dirs_follows_a_declared_source(tmp_path):
    "The manifest, not the folder convention, says where a plugin is."
    checkout = tmp_path / "marketplaces" / "acme"
    plugin = checkout / "vendored" / "documents"
    (plugin / "skills" / "pdf").mkdir(parents=True)
    (checkout / ".claude-plugin").mkdir(parents=True)
    (checkout / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "acme",
                "plugins": [{"name": "documents", "source": "./vendored/documents"}],
            }
        ),
        encoding="utf-8",
    )
    assert plugin in scan_plugin_dirs(tmp_path)


def test_scan_plugin_dirs_ignores_a_remote_source(tmp_path):
    "A github/npm source is not on this disk to read."
    checkout = tmp_path / "marketplaces" / "acme"
    (checkout / ".claude-plugin").mkdir(parents=True)
    (checkout / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "acme",
                "plugins": [
                    {"name": "remote", "source": "github", "repo": "acme/remote"},
                    {"name": "odd", "source": 3},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert scan_plugin_dirs(tmp_path) == [checkout]


def test_scan_plugin_dirs_ignores_a_malformed_marketplace_manifest(tmp_path):
    checkout = tmp_path / "marketplaces" / "acme"
    (checkout / ".claude-plugin").mkdir(parents=True)
    (checkout / ".claude-plugin" / "marketplace.json").write_text(
        "{not json", encoding="utf-8"
    )
    assert scan_plugin_dirs(tmp_path) == [checkout]


def test_scan_plugin_dirs_rejects_a_source_outside_the_checkout(
    tmp_path, tmp_path_factory
):
    "A manifest is data, not a grant: it may not name a directory it does not own."
    outside = tmp_path_factory.mktemp("outside")
    (outside / "skills" / "pdf").mkdir(parents=True)
    checkout = tmp_path / "marketplaces" / "acme"
    (checkout / ".claude-plugin").mkdir(parents=True)
    (checkout / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "acme",
                "plugins": [
                    {"name": "absolute", "source": str(outside)},
                    {"name": "climbing", "source": "../outside"},
                ],
            }
        ),
        encoding="utf-8",
    )
    plugin_dirs = [path.resolve() for path in scan_plugin_dirs(tmp_path)]
    assert outside.resolve() not in plugin_dirs
    assert plugin_dirs == [checkout.resolve()]


def test_scan_plugin_dirs_rejects_a_symlink_out_of_the_checkout(
    tmp_path, tmp_path_factory
):
    outside = tmp_path_factory.mktemp("outside")
    (outside / ".claude-plugin").mkdir(parents=True)
    (outside / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    checkout = tmp_path / "marketplaces" / "acme"
    (checkout / "plugins").mkdir(parents=True)
    try:
        (checkout / "plugins" / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available in this environment")
    plugin_dirs = [path.resolve() for path in scan_plugin_dirs(tmp_path)]
    assert outside.resolve() not in plugin_dirs


def test_scan_plugin_dirs_tolerates_unexpected_marketplace_shapes(tmp_path):
    checkout = tmp_path / "marketplaces" / "acme"
    manifest = checkout / ".claude-plugin" / "marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"plugins": "nope"}), encoding="utf-8")
    assert scan_plugin_dirs(tmp_path) == [checkout]
    manifest.write_text(json.dumps([]), encoding="utf-8")
    assert scan_plugin_dirs(tmp_path) == [checkout]


def test_scan_plugin_dirs_prefers_the_installed_copy(tmp_path):
    "A later directory wins a collision, so the version Claude Code loads comes last."
    checkout = tmp_path / "marketplaces" / "market"
    (checkout / "skills").mkdir(parents=True)
    installed = tmp_path / "cache" / "market" / "documents" / "abc123"
    installed.mkdir(parents=True)
    _write_plugin_index(
        tmp_path, {"documents@market": [{"installPath": str(installed)}]}
    )
    plugin_dirs = scan_plugin_dirs(tmp_path)
    assert plugin_dirs.index(installed) > plugin_dirs.index(checkout)


def test_scan_plugin_dirs_skips_install_paths_that_are_gone(tmp_path):
    _write_plugin_index(
        tmp_path, {"documents@market": [{"installPath": str(tmp_path / "uninstalled")}]}
    )
    assert scan_plugin_dirs(tmp_path) == []


def test_scan_plugin_dirs_ignores_a_malformed_index(tmp_path):
    (tmp_path / "installed_plugins.json").write_text("{not json", encoding="utf-8")
    assert scan_plugin_dirs(tmp_path) == []


def test_scan_plugin_dirs_tolerates_unexpected_index_shapes(tmp_path):
    index_path = tmp_path / "installed_plugins.json"
    index_path.write_text(json.dumps({"plugins": ["nope"]}), encoding="utf-8")
    assert scan_plugin_dirs(tmp_path) == []
    index_path.write_text(json.dumps([]), encoding="utf-8")
    assert scan_plugin_dirs(tmp_path) == []
    index_path.write_text(
        json.dumps({"plugins": {"p": [{"installPath": 3}, "not-a-dict"]}}),
        encoding="utf-8",
    )
    assert scan_plugin_dirs(tmp_path) == []


def test_scan_plugin_dirs_survives_an_unreadable_index(tmp_path):
    (tmp_path / "installed_plugins.json").write_text("{}", encoding="utf-8")
    with patch.object(Path, "read_text", side_effect=OSError("denied")):
        assert scan_plugin_dirs(tmp_path) == []


def test_scan_plugin_dirs_survives_an_unreadable_root(tmp_path):
    (tmp_path / "marketplaces").mkdir()
    with patch.object(Path, "iterdir", side_effect=OSError("denied")):
        assert scan_plugin_dirs(tmp_path) == []


def test_get_dirs_up_to_home_walks_nearest_first(tmp_path):
    home = str(tmp_path)
    nested = str(tmp_path / "a" / "b")
    assert get_dirs_up_to_home(nested, home) == [
        nested,
        str(tmp_path / "a"),
        home,
    ]


def test_get_dirs_up_to_home_outside_home_is_start_only(tmp_path):
    outside = str(tmp_path / "elsewhere")
    assert get_dirs_up_to_home(outside, str(tmp_path / "home")) == [outside]


def test_get_dirs_up_to_home_other_drive_is_start_only():
    with patch("os.path.commonpath", side_effect=ValueError("different drives")):
        assert get_dirs_up_to_home("/x/y", "/x") == ["/x/y"]


def test_split_config_dir_patterns_keeps_names_and_absolute_roots_apart(tmp_path):
    root = str(tmp_path / "config")
    names, roots = split_config_dir_patterns([".claude", root, ".zrb"])
    assert names == [".claude", ".zrb"]
    assert roots == [Path(root)]


def test_split_config_dir_patterns_expands_a_tilde_root(tmp_path):
    # A platform's own absolute path: "/home/someone" carries no drive on
    # Windows and would be read as a name there.
    expanded = str(tmp_path / "claude-alt")
    with patch("os.path.expanduser", return_value=expanded):
        names, roots = split_config_dir_patterns(["~/.claude-alt"])
    assert names == []
    assert roots == [Path(expanded)]


def test_split_config_dir_patterns_drops_blank_and_repeated_entries():
    names, roots = split_config_dir_patterns([".claude", "  ", ".claude", ".zrb"])
    assert names == [".claude", ".zrb"]
    assert roots == []


def test_split_config_dir_patterns_of_nothing_is_nothing():
    assert split_config_dir_patterns([]) == ([], [])
