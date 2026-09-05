from unittest.mock import MagicMock, patch

from zrb.builtin.setup.asdf.asdf import (
    setup_asdf,
    setup_asdf_on_bash,
    setup_asdf_on_powershell,
    setup_asdf_on_zsh,
)


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_setup_asdf_on_bash():
    ctx = MagicMock()
    with patch("zrb.builtin.setup.asdf.asdf.setup_asdf_sh_config") as mock_setup:
        _action(setup_asdf_on_bash)(ctx)
        mock_setup.assert_called_once()


def test_setup_asdf_on_zsh():
    ctx = MagicMock()
    with patch("zrb.builtin.setup.asdf.asdf.setup_asdf_sh_config") as mock_setup:
        _action(setup_asdf_on_zsh)(ctx)
        mock_setup.assert_called_once()


def test_setup_asdf_on_powershell():
    ctx = MagicMock()
    with patch("zrb.builtin.setup.asdf.asdf.setup_asdf_ps_config") as mock_setup:
        _action(setup_asdf_on_powershell)(ctx)
        mock_setup.assert_called_once()


def test_setup_asdf_main():
    ctx = MagicMock()
    _action(setup_asdf)(ctx)
    assert ctx.print.called
