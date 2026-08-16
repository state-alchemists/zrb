import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.setup.zsh.zsh import setup_zsh


def test_setup_zsh_new_file():
    ctx = MagicMock()
    ctx.input = {"zsh-config": "/tmp/.zshrc"}

    with (
        patch(
            "zrb.builtin.setup.zsh.zsh.read_file",
            return_value="ZSH_CONFIG_TEMPLATE",
        ),
        patch("zrb.builtin.setup.config_file_helper.read_file", return_value=""),
        patch("os.path.expanduser", return_value="/tmp/.zshrc"),
        patch("os.path.isfile", return_value=False),
        patch("zrb.builtin.setup.config_file_helper.write_file") as mock_write,
    ):

        setup_zsh._action(ctx)

        assert mock_write.call_count == 2
        assert ctx.print.called


def test_setup_zsh_existing_config():
    ctx = MagicMock()
    ctx.input = {"zsh-config": "/tmp/.zshrc"}

    # Simulate config already in file (template read and target-file read
    # return the same content, so the "already contains config" check hits)
    with (
        patch("zrb.builtin.setup.zsh.zsh.read_file", return_value="MY_ZSH_CONFIG"),
        patch(
            "zrb.builtin.setup.config_file_helper.read_file",
            return_value="MY_ZSH_CONFIG",
        ),
        patch("os.path.expanduser", return_value="/tmp/.zshrc"),
        patch("os.path.isfile", return_value=True),
        patch("zrb.builtin.setup.config_file_helper.write_file") as mock_write,
    ):

        setup_zsh._action(ctx)

        assert mock_write.call_count == 0
        assert not ctx.print.called
