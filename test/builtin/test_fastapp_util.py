import os
from unittest.mock import MagicMock

import pytest

from zrb.builtin.project.add.fastapp.fastapp_util import (
    is_in_project_app_dir,
    is_project_zrb_init_file,
)
from zrb.dot_dict.dot_dict import DotDict


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.input = DotDict({"project_dir": "/path/to/project", "app": "MyApp"})
    return ctx


def test_is_in_project_app_dir(mock_ctx):
    # App name 'MyApp' becomes 'my_app' via to_snake_case
    app_dir = os.path.abspath("/path/to/project/my_app")
    assert is_in_project_app_dir(mock_ctx, os.path.join(app_dir, "main.py")) is True
    assert is_in_project_app_dir(mock_ctx, "/path/to/project/other/main.py") is False


def test_is_project_zrb_init_file(mock_ctx):
    zrb_init = os.path.abspath("/path/to/project/zrb_init.py")
    assert is_project_zrb_init_file(mock_ctx, zrb_init) is True
    assert is_project_zrb_init_file(mock_ctx, "/path/to/project/main.py") is False
