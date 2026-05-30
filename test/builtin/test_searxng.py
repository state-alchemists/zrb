import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zrb.builtin.searxng.start import copy_searxng_setting


def test_copy_searxng_setting(tmp_path):
    ctx = MagicMock()
    mock_home = str(tmp_path / "home")

    dest_dir = os.path.join(mock_home, ".config", "searxng")
    dest_settings = os.path.join(dest_dir, "settings.yml")
    dest_limiter = os.path.join(dest_dir, "limiter.toml")

    fake_content = '"ultrasecretkey"'

    with patch("os.path.expanduser", return_value=mock_home), patch(
        "os.path.isfile", return_value=False
    ), patch("os.makedirs"), patch(
        "zrb.builtin.searxng.start.open", mock_open(read_data=fake_content)
    ) as mock_file, patch(
        "shutil.copy"
    ) as mock_copy:

        copy_searxng_setting._action(ctx)

        assert ctx.print.called
        mock_file.assert_called()
        mock_copy.assert_called_once()
