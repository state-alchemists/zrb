import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.setup.tmux.tmux import setup_tmux


def test_setup_tmux_new_file():
    ctx = MagicMock()
    ctx.input = {"tmux-config": "/tmp/.tmux.conf"}

    with (
        patch("zrb.builtin.setup.tmux.tmux.read_file", return_value="SKILL_CONTENT"),
        patch("zrb.builtin.setup.config_file_helper.read_file", return_value=""),
        patch("os.path.expanduser", return_value="/tmp/.tmux.conf"),
        patch("os.path.isfile", return_value=False),
        patch("zrb.builtin.setup.config_file_helper.write_file") as mock_write,
    ):

        setup_tmux._action(ctx)

        # Should be called twice: once to ensure file exists, once to append config
        assert mock_write.call_count == 2
        assert ctx.print.called


def test_setup_tmux_existing_config():
    ctx = MagicMock()
    ctx.input = {"tmux-config": "/tmp/.tmux.conf"}

    # Simulate config already in file (template read and target-file read
    # return the same content, so the "already contains config" check hits)
    with (
        patch("zrb.builtin.setup.tmux.tmux.read_file", return_value="MY_CONFIG"),
        patch(
            "zrb.builtin.setup.config_file_helper.read_file",
            return_value="MY_CONFIG",
        ),
        patch("os.path.expanduser", return_value="/tmp/.tmux.conf"),
        patch("os.path.isfile", return_value=True),
        patch("zrb.builtin.setup.config_file_helper.write_file") as mock_write,
    ):

        setup_tmux._action(ctx)

        # Should NOT write anything if config already exists, and must not
        # print "setup complete" for a no-op run.
        assert mock_write.call_count == 0
        assert not ctx.print.called
