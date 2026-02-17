import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.project.add.fastapp.fastapp_task import validate_add_fastapp
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.task.base.context import fill_shared_context_inputs


@pytest.fixture
def session():
    shared_ctx = SharedContext()
    return Session(shared_ctx=shared_ctx, state_logger=MagicMock())


@pytest.mark.asyncio
async def test_validate_add_fastapp_success(tmp_path, session):
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    fill_shared_context_inputs(
        session.shared_ctx,
        validate_add_fastapp,
        kwargs={"project_dir": str(project_dir), "app": "my-app"},
    )

    # Execute publicly
    await validate_add_fastapp.exec(session)


@pytest.mark.asyncio
async def test_validate_add_fastapp_project_not_exists(tmp_path, session):
    fill_shared_context_inputs(
        session.shared_ctx,
        validate_add_fastapp,
        kwargs={"project_dir": str(tmp_path / "non_existent"), "app": "my-app"},
    )

    with pytest.raises(ValueError, match="Project directory not exists"):
        await validate_add_fastapp.exec(session)


@pytest.mark.asyncio
async def test_validate_add_fastapp_app_exists(tmp_path, session):
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    (project_dir / "my_app").mkdir()  # snake_case of my-app

    fill_shared_context_inputs(
        session.shared_ctx,
        validate_add_fastapp,
        kwargs={"project_dir": str(project_dir), "app": "my-app"},
    )

    with pytest.raises(ValueError, match="Application directory already exists"):
        await validate_add_fastapp.exec(session)
