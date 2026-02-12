import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.project.add.fastapp.fastapp_task import validate_add_fastapp
from zrb.context.any_context import AnyContext
from zrb.dot_dict.dot_dict import DotDict


@pytest.mark.asyncio
async def test_validate_add_fastapp_success(tmp_path):
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    ctx = MagicMock(spec=AnyContext)
    ctx.input = DotDict({"project_dir": str(project_dir), "app": "my-app"})

    # Access the underlying action directly
    await validate_add_fastapp._action(ctx)


@pytest.mark.asyncio
async def test_validate_add_fastapp_project_not_exists(tmp_path):
    ctx = MagicMock(spec=AnyContext)
    ctx.input = DotDict(
        {"project_dir": str(tmp_path / "non_existent"), "app": "my-app"}
    )

    with pytest.raises(ValueError, match="Project directory not exists"):
        await validate_add_fastapp._action(ctx)


@pytest.mark.asyncio
async def test_validate_add_fastapp_app_exists(tmp_path):
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    (project_dir / "my_app").mkdir()  # snake_case of my-app

    ctx = MagicMock(spec=AnyContext)
    ctx.input = DotDict({"project_dir": str(project_dir), "app": "my-app"})

    with pytest.raises(ValueError, match="Application directory already exists"):
        await validate_add_fastapp._action(ctx)
