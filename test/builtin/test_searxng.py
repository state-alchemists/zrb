import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.searxng.start import copy_searxng_setting


def test_copy_searxng_setting(tmp_path):
    ctx = MagicMock()
    mock_home = str(tmp_path / "home")

    # Path where settings would go
    dest_dir = os.path.join(mock_home, ".config", "searxng")
    dest_file = os.path.join(dest_dir, "settings.yml.new")

    with patch("os.path.expanduser", return_value=mock_home), patch(
        "os.path.isfile", return_value=False
    ), patch("shutil.copy") as mock_copy, patch("os.makedirs") as mock_mkdir:

        copy_searxng_setting._action(ctx)

        # Verify it tried to create dir and copy
        mock_mkdir.assert_called_once_with(dest_dir, exist_ok=True)
        mock_copy.assert_called_once()
        assert ctx.print.called
