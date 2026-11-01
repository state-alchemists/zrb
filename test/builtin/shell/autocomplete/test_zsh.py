import shutil
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from zrb.builtin.shell.autocomplete.zsh import make_zsh_autocomplete
from zrb.config.config import CFG


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_make_zsh_autocomplete_uses_default_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_zsh_autocomplete)(ctx)
    assert "_zrb_complete()" in script
    assert "compdef _zrb_complete zrb" in script
    assert "zrb shell autocomplete subcmd" in script


def test_make_zsh_autocomplete_renames_custom_root_group_name(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "myapp")
    ctx = MagicMock()
    script = _action(make_zsh_autocomplete)(ctx)
    assert "_myapp_complete()" in script
    assert "compdef _myapp_complete myapp" in script
    assert "myapp shell autocomplete subcmd" in script
    assert "_zrb_complete()" not in script
    assert "compdef _zrb_complete zrb" not in script


def test_make_zsh_autocomplete_caches_subcommand_output(monkeypatch):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "zrb")
    ctx = MagicMock()
    script = _action(make_zsh_autocomplete)(ctx)
    assert "cache_file=" in script
    assert 'find "$cache_file" -mmin -1' in script


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("zsh") is None,
    reason="needs a POSIX zsh",
)
def test_make_zsh_autocomplete_does_not_execute_typed_words(monkeypatch, tmp_path):
    monkeypatch.setattr(CFG, "ROOT_GROUP_NAME", "fakecli")
    script = _action(make_zsh_autocomplete)(MagicMock())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "argv.log"
    marker = tmp_path / "marker"
    fake_cli = bin_dir / "fakecli"
    fake_cli.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGV_LOG"\necho alpha beta\n'
    )
    fake_cli.chmod(0o755)
    driver = tmp_path / "driver.zsh"
    # `compdef` and `_describe` only exist inside zsh's completion system, so
    # stand them in; `_describe` prints the candidates it is given.
    driver.write_text(
        """
compdef() { :; }
_describe() { print -rl -- "${(@P)2}"; }
"""
        + script
        + f"""
words=(fakecli 'x$(touch {marker})' '`touch {marker}`' '')
CURRENT=4
_fakecli_complete
"""
    )

    result = subprocess.run(
        ["zsh", "-f", str(driver)],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "ARGV_LOG": str(argv_log),
        },
    )

    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    # The command gets the typed words verbatim, one argument each.
    assert argv_log.read_text().splitlines() == [
        "shell",
        "autocomplete",
        "subcmd",
        "fakecli",
        f"x$(touch {marker})",
        f"`touch {marker}`",
    ]
    assert result.stdout.split() == ["alpha", "beta"]
