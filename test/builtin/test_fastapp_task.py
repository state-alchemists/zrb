import pytest

from zrb.builtin.project.add.fastapp.fastapp_task import validate_add_fastapp
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.mark.asyncio
async def test_validate_add_fastapp_success(tmp_path):
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    task = validate_add_fastapp
    session = get_fresh_session()
    await task.async_run(
        session=session,
        kwargs={"project_dir": str(project_dir), "app": "my-app"},
    )


@pytest.mark.asyncio
async def test_validate_add_fastapp_project_not_exists(tmp_path):
    task = validate_add_fastapp
    session = get_fresh_session()
    with pytest.raises(ValueError, match="Project directory not exists"):
        await task.async_run(
            session=session,
            kwargs={
                "project_dir": str(tmp_path / "non_existent"),
                "app": "my-app",
            },
        )


@pytest.mark.asyncio
async def test_validate_add_fastapp_app_exists(tmp_path):
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    (project_dir / "my_app").mkdir()  # snake_case of my-app

    task = validate_add_fastapp
    session = get_fresh_session()
    with pytest.raises(ValueError, match="Application directory already exists"):
        await task.async_run(
            session=session,
            kwargs={"project_dir": str(project_dir), "app": "my-app"},
        )
