from unittest.mock import MagicMock

from zrb.builtin.shell.autocomplete.powershell import make_powershell_autocomplete
from zrb.config.config import CFG


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_make_powershell_autocomplete_uses_default_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_powershell_autocomplete)(ctx)
    assert "-CommandName 'zrb'" in script
    assert "zrb shell autocomplete subcmd" in script


def test_make_powershell_autocomplete_renames_custom_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "myapp")
    ctx = MagicMock()
    script = _action(make_powershell_autocomplete)(ctx)
    assert "-CommandName 'myapp'" in script
    assert "myapp shell autocomplete subcmd" in script
    assert "-CommandName 'zrb'" not in script


def test_make_powershell_autocomplete_caches_subcommand_output(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_powershell_autocomplete)(ctx)
    assert "$cacheFile" in script
    assert "AddMinutes(-1)" in script
