import os
import sys

from zrb import (
    AnyContext,
    CmdPath,
    CmdTask,
    Env,
    Group,
    StrInput,
    Task,
    TcpCheck,
    cli,
    make_task,
)
from zrb.builtin.git import git_commit
from zrb.builtin.project.add.fastapp import add_fastapp_to_project
from zrb.builtin.project.create.create import create_project
from zrb.util.load import load_file

_DIR = os.path.dirname(__file__)

# TEST =======================================================================

test_group = cli.add_group(Group("test", description="🔍 Testing zrb codebase"))

clean_up_test_resources = CmdTask(
    name="clean-up-resources",
    cwd=os.path.join(_DIR, "test"),
    cmd=["sudo -k rm -Rf task/scaffolder/generated"],
)

start_test_docker_compose = CmdTask(
    name="start-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down && docker compose up",
    readiness_check=TcpCheck(name="check-start-test-compose", port=2222),
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
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down",
)
run_test >> stop_test_docker_compose

prepare_and_run_test = test_group.add_task(
    Task(
        name="run-test",
        action=lambda ctx: ctx.xcom["run-integration-test"].pop(),
        cli_only=True,
    ),
    alias="run",
)
stop_test_docker_compose >> prepare_and_run_test


# CODE ========================================================================

code_group = cli.add_group(Group("code", description="📜 Code related command"))

format_code = code_group.add_task(
    CmdTask(
        name="format-code",
        description="Format Zrb code",
        cwd=_DIR,
        cmd=CmdPath(os.path.join(_DIR, "zrb-format-code.sh")),
    ),
    alias="format",
)
format_code >> git_commit


# PIP =========================================================================

pip_group = cli.add_group(
    Group(name="pip", description="📦 Pip related command")
)

publish_pip = pip_group.add_task(
    CmdTask(
        name="publish-pip",
        description="Publish Zrb",
        cwd=_DIR,
        cmd=CmdPath(os.path.join(_DIR, "zrb-publish.sh")),
    ),
    alias="publish",
)
format_code >> publish_pip

# GENERATOR TEST ==============================================================

remove_generated = cli.add_task(
    CmdTask(
        name="remove-generated",
        description="🔄 Remove generated resources",
        cmd=f"rm -Rf {os.path.join(_DIR, 'playground', 'generated')}",
        render_cmd=False,
    )
)


@make_task(
    name="test-generate-fastapp",
    description="🔨 Test generate fastapp",
    group=test_group,
    alias="generate"
)
async def test_generate(ctx: AnyContext):
    # Create project
    ctx.print("Create project")
    project_dir = os.path.join(_DIR, "playground", "generated")
    project_name = "Amalgam"
    await create_project.async_run(
        str_kwargs={"project-dir": project_dir, "project": project_name}
    )
    assert os.path.isfile(os.path.join(project_dir, "zrb_init.py"))

    # Create fastapp
    ctx.print("Add fastapp")
    app_name = "fastapp"
    await add_fastapp_to_project.async_run(
        str_kwargs={"project-dir": project_dir, "app": app_name}
    )
    assert os.path.isdir(os.path.join(project_dir, app_name))

    # Get fastapp task path
    app_dir_path = os.path.join(project_dir, app_name)
    app_task_path = os.path.join(app_dir_path, "_zrb", "main.py")

    # Load fastapp task
    ctx.print("Load fastapp tasks")
    assert os.path.isfile(app_task_path)
    sys.path.insert(0, os.path.dirname(app_dir_path))
    app_task = load_file(app_task_path)

    # Create module
    ctx.print("Create module")
    create_fastapp_module = app_task.create_fastapp_module
    await create_fastapp_module.async_run(str_kwargs={"module": "library"})
    assert os.path.isdir(os.path.join(app_dir_path, "module", "library"))
    # Second test: create entity
    ctx.print("Create entity")
    create_fastapp_entity = app_task.create_fastapp_entity
    await create_fastapp_entity.async_run(
        str_kwargs={
            "module": "library",
            "entity": "book",
            "plural": "books",
            "column": "title"
        }
    )
    assert os.path.isfile(os.path.join(app_dir_path, "schema", "book.py"))

    # Reload module
    ctx.print("Reload fastapp tasks")
    app_task = load_file(app_task_path, reload=True)

    # Create migration
    ctx.print("Create migration")
    create_library_migration = app_task.create_library_migration
    await create_library_migration.async_run(
        str_kwargs={"message": "create book table"}
    )

    # Start microservices
    ctx.print("Run microservices")
    run_microservices = app_task.run_microservices
    await run_microservices.async_run()


remove_generated >> test_generate


# PLAYGROUND ==================================================================

playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    load_file(playground_zrb_init_path)
