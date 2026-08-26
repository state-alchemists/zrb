from unittest.mock import MagicMock

from zrb.builtin.shell.autocomplete.zsh import make_zsh_autocomplete
from zrb.config.config import CFG


def test_make_zsh_autocomplete_uses_default_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = make_zsh_autocomplete.action(ctx)
    assert "_zrb_complete()" in script
    assert "compdef _zrb_complete zrb" in script
    assert "zrb shell autocomplete subcmd" in script


def test_make_zsh_autocomplete_renames_custom_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "myapp")
    ctx = MagicMock()
    script = make_zsh_autocomplete.action(ctx)
    assert "_myapp_complete()" in script
    assert "compdef _myapp_complete myapp" in script
    assert "myapp shell autocomplete subcmd" in script
    assert "_zrb_complete()" not in script
    assert "compdef _zrb_complete zrb" not in script


def test_make_zsh_autocomplete_caches_subcommand_output(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = make_zsh_autocomplete.action(ctx)
    assert "cache_file=" in script
    assert 'find "$cache_file" -mmin -1' in script
