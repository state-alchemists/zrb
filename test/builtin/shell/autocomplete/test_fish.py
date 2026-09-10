from unittest.mock import MagicMock

from zrb.builtin.shell.autocomplete.fish import make_fish_autocomplete
from zrb.config.config import CFG


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_make_fish_autocomplete_uses_default_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_fish_autocomplete)(ctx)
    assert "function __zrb_complete" in script
    assert "complete -c zrb -f -a '(__zrb_complete)'" in script
    assert "zrb shell autocomplete subcmd" in script


def test_make_fish_autocomplete_renames_custom_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "myapp")
    ctx = MagicMock()
    script = _action(make_fish_autocomplete)(ctx)
    assert "function __myapp_complete" in script
    assert "complete -c myapp -f -a '(__myapp_complete)'" in script
    assert "myapp shell autocomplete subcmd" in script
    assert "function __zrb_complete" not in script
    assert "complete -c zrb -f -a '(__zrb_complete)'" not in script


def test_make_fish_autocomplete_caches_subcommand_output(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_fish_autocomplete)(ctx)
    assert "cache_file" in script
    assert 'find "$cache_file" -mmin -1' in script
