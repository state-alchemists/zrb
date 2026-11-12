"""Hook discovery follows ``LLM_CONFIG_DIR_NAMES``, names and absolute roots alike."""

from pathlib import Path
from unittest.mock import patch

from zrb.llm.hook import hook_loader


def _write_json(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path


def _search_dirs_under(home: Path) -> list[str | Path]:
    with patch.object(hook_loader.Path, "home", return_value=home):
        return hook_loader.get_search_directories()


def test_a_named_config_dir_is_read_under_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    settings = _write_json(home / ".claude-alt" / "settings.json")
    monkeypatch.setenv("ZRB_LLM_CONFIG_DIR_NAMES", ".claude-alt")
    assert settings in _search_dirs_under(home)


def test_an_absolute_config_root_is_read_under_home(
    tmp_path, tmp_path_factory, monkeypatch
):
    "``$CLAUDE_CONFIG_DIR`` is the config directory itself, not one under home."
    config_root = tmp_path_factory.mktemp("claude-alt")
    settings = _write_json(config_root / "settings.json")
    monkeypatch.setenv("ZRB_LLM_CONFIG_DIR_NAMES", str(config_root))
    assert settings in _search_dirs_under(tmp_path / "home")


def test_zrb_hooks_are_read_even_when_the_name_list_drops_zrb(tmp_path, monkeypatch):
    home = tmp_path / "home"
    zrb_hooks = _write_json(home / ".zrb" / "hooks.json")
    monkeypatch.setenv("ZRB_LLM_CONFIG_DIR_NAMES", ".claude")
    assert zrb_hooks in _search_dirs_under(home)
