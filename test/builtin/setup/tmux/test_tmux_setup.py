import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.setup.tmux.tmux import setup_tmux


def test_setup_tmux_new_file():
    ctx = MagicMock()
    ctx.input = {"tmux-config": "/tmp/.tmux.conf"}

    with patch(
        "zrb.builtin.setup.tmux.tmux.read_file", side_effect=["SKILL_CONTENT", ""]
    ), patch("os.path.expanduser", return_value="/tmp/.tmux.conf"), patch(
        "os.path.isfile", return_value=False
    ), patch(
        "zrb.builtin.setup.tmux.tmux.write_file"
    ) as mock_write:

        setup_tmux._action(ctx)

        # Should be called twice: once to ensure file exists, once to append config
        assert mock_write.call_count == 2
        assert ctx.print.called


def test_setup_tmux_existing_config():
    ctx = MagicMock()
    ctx.input = {"tmux-config": "/tmp/.tmux.conf"}

    # Simulate config already in file
    with patch(
        "zrb.builtin.setup.tmux.tmux.read_file", side_effect=["MY_CONFIG", "MY_CONFIG"]
    ), patch("os.path.expanduser", return_value="/tmp/.tmux.conf"), patch(
        "os.path.isfile", return_value=True
    ), patch(
        "zrb.builtin.setup.tmux.tmux.write_file"
    ) as mock_write:

        setup_tmux._action(ctx)

        # Should NOT write anything if config already exists
        assert mock_write.call_count == 0
