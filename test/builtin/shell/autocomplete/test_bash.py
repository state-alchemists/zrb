from unittest.mock import MagicMock

from zrb.builtin.shell.autocomplete.bash import make_bash_autocomplete
from zrb.config.config import CFG


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_make_bash_autocomplete_uses_default_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_bash_autocomplete)(ctx)
    assert "_zrb_complete()" in script
    assert "complete -F _zrb_complete zrb" in script
    assert "zrb shell autocomplete subcmd" in script


def test_make_bash_autocomplete_renames_custom_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "myapp")
    ctx = MagicMock()
    script = _action(make_bash_autocomplete)(ctx)
    assert "_myapp_complete()" in script
    assert "complete -F _myapp_complete myapp" in script
    assert "myapp shell autocomplete subcmd" in script
    assert "_zrb_complete()" not in script
    assert "complete -F _zrb_complete zrb" not in script


def test_make_bash_autocomplete_caches_subcommand_output(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_bash_autocomplete)(ctx)
    assert "cache_file=" in script
    assert 'find "$cache_file" -mmin -1' in script
