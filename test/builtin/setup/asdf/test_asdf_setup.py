import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.setup.asdf.asdf import (
    setup_asdf,
    setup_asdf_on_bash,
    setup_asdf_on_powershell,
    setup_asdf_on_zsh,
)


def test_setup_asdf_on_bash():
    ctx = MagicMock()
    with patch("zrb.builtin.setup.asdf.asdf.setup_asdf_sh_config") as mock_setup:
        setup_asdf_on_bash._action(ctx)
        mock_setup.assert_called_once()


def test_setup_asdf_on_zsh():
    ctx = MagicMock()
    with patch("zrb.builtin.setup.asdf.asdf.setup_asdf_sh_config") as mock_setup:
        setup_asdf_on_zsh._action(ctx)
        mock_setup.assert_called_once()


def test_setup_asdf_on_powershell():
    ctx = MagicMock()
    with patch("zrb.builtin.setup.asdf.asdf.setup_asdf_ps_config") as mock_setup:
        setup_asdf_on_powershell._action(ctx)
        mock_setup.assert_called_once()


def test_setup_asdf_main():
    ctx = MagicMock()
    setup_asdf._action(ctx)
    assert ctx.print.called
