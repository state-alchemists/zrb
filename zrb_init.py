from zrb import (
    AnyContext, Task, CmdTask, CmdPath, Env, TcpCheck, StrInput, Group, cli, make_task
)
from zrb.builtin.project.create.create import create_project
from zrb.builtin.project.add.fastapp import add_fastapp_to_project
from zrb.builtin.git import git_commit
from zrb.util.load import load_file
import os

_DIR = os.path.dirname(__file__)

# TEST ==============================================================================

test_group = cli.add_group(Group("test", description="🔍 Testing zrb codebase"))

clean_up_test_resources = CmdTask(
    name="clean-up-resources",
    cwd=os.path.join(_DIR, "test"),
    cmd=[
        "sudo -k rm -Rf task/scaffolder/test-generated"
    ]
)

start_test_docker_compose = CmdTask(
    name="start-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down && docker compose up",
    readiness_check=TcpCheck(
        name="check-start-test-compose",
        port=2222
    )
)
clean_up_test_resources >> start_test_docker_compose

run_test = CmdTask(
    name="run-integration-test",
    input=StrInput(
        name="test",
        description="Specific test case (i.e., test/file.py::test_name)",
        prompt="Test (i.e., test/file.py::test_name)",
        default_str="",
    ),
    env=Env(name="TEST", default="{ctx.input.test}", link_to_os=False),
    cwd=_DIR,
    cmd=CmdPath(os.path.join(_DIR, "zrb-test.sh"), auto_render=False),
    retries=0,
)
start_test_docker_compose >> run_test

stop_test_docker_compose = CmdTask(
    name="stop-test-compose",
    description="Start docker compose for testing, run test, then remove the docker compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down"
)
run_test >> stop_test_docker_compose

prepare_and_run_test = test_group.add_task(
    Task(
        name="run-test",
        action=lambda ctx: ctx.xcom["run-integration-test"].pop(),
        cli_only=True
    ),
    alias="run"
)
stop_test_docker_compose >> prepare_and_run_test


# CODE ===============================================================================

code_group = cli.add_group(Group("code", description="📜 Code related command"))

format_code = code_group.add_task(
    CmdTask(
        name="format-code",
        description="Format Zrb code",
        cwd=_DIR,
        cmd=CmdPath(os.path.join(_DIR, "zrb-format-code.sh"))
    ),
    alias="format"
)
format_code >> git_commit


# PIP ===============================================================================

pip_group = cli.add_group(Group(name="pip", description="📦 Pip related command"))

publish_pip = pip_group.add_task(
    CmdTask(
        name="publish-pip",
        description="Publish Zrb",
        cwd=_DIR,
        cmd=CmdPath(os.path.join(_DIR, "zrb-publish.sh"))
    ),
    alias="publish"
)
format_code >> publish_pip

# GENERATOR TEST ====================================================================

clean_up_test_generator_resources = CmdTask(
    name="clean-up-resources",
    cmd=f"rm -Rf {os.path.join(_DIR, 'amalgam')}",
    auto_render_cmd=False
)


@make_task(
    name="test-generator",
    group=test_group,
    alias="generator"
)
async def test_generator(ctx: AnyContext):
    # Test create project
    ctx.print("Create project")
    project_dir = os.path.join(_DIR, "amalgam")
    project_name = "Amalgam"
    await create_project.async_run(
        str_kwargs={"project-dir": project_dir, "project-name": project_name}
    )
    assert os.path.isfile(os.path.join(project_dir, "zrb_init.py"))
    # Test create fastapp
    ctx.print("Add fastapp")
    app_name = "fastapp"
    await add_fastapp_to_project.async_run(
        str_kwargs={"project-dir": project_dir, "app-name": app_name}
    )
    assert os.path.isdir(os.path.join(project_dir, app_name))
    # Done
    ctx.print("Done")


clean_up_test_generator_resources >> test_generator


# PLAYGROUND ========================================================================

playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    load_file(playground_zrb_init_path)

# AMALGAM ===========================================================================

amalgam_zrb_init_path = os.path.join(_DIR, "amalgam", "zrb_init.py")
if os.path.isfile(amalgam_zrb_init_path):
    load_file(amalgam_zrb_init_path)
