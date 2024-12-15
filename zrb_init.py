import os
from typing import Any

import tomlkit

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
from zrb.cmd.cmd_val import CmdVal
from zrb.util.cli.style import WHITE
from zrb.util.file import read_file
from zrb.util.load import load_file

_DIR = os.path.dirname(__file__)

_PYPROJECT = tomlkit.loads(read_file(os.path.join(_DIR, "pyproject.toml")))
_VERSION = _PYPROJECT["tool"]["poetry"]["version"]


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
        cmd=[
            "isort src",
            "black src",
            "isort test",
            "black test",
            "isort zrb_init.py",
            "black zrb_init.py",
        ],
    ),
    alias="format",
)
format_code >> git_commit

# DOCKER =======================================================================

docker_group = cli.add_group(
    Group(name="docker", description="🐋 Docker related command")
)

build_docker = docker_group.add_task(
    CmdTask(
        name="build-zrb-docker-image",
        description="Build Zrb docker image",
        cwd=_DIR,
        cmd=f"docker build . -t stalchmst/zrb:{_VERSION}",
    ),
    alias="build",
)
format_code >> build_docker

run_docker = docker_group.add_task(
    CmdTask(
        name="run-zrb-docker-container",
        description="Run Zrb docker container",
        cwd=_DIR,
        cmd=f"docker run -p 21213:21213 --rm stalchmst/zrb:{_VERSION}",
    ),
    alias="run",
)
build_docker >> run_docker

publish_docker = docker_group.add_task(
    CmdTask(
        name="publish-zrb-docker-image",
        description="Publish Zrb docker image",
        cwd=_DIR,
        cmd=f"docker push stalchmst/zrb:{_VERSION}",
    ),
    alias="publish",
)
build_docker >> publish_docker

# PUBLISH ======================================================================

publish_group = cli.add_group(
    Group(name="publish", description="📦 Publication related command")
)

publish_pip = publish_group.add_task(
    CmdTask(
        name="publish-zrb-to-pip",
        description="Publish Zrb as pip package",
        cwd=_DIR,
        cmd="poetry publish --build",
    ),
    alias="pip",
)
format_code >> publish_pip

publish_group.add_task(publish_docker, alias="docker")

publish_all = publish_group.add_task(
    Task(name="publish-all", description="Publish Zrb")
)
publish_all << [publish_pip, publish_docker]

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
    alias="generate",
    retries=0,
)
async def test_generate(ctx: AnyContext):
    # Create project
    project_dir = os.path.join(_DIR, "playground", "generated")
    project_name = "Amalgam"
    await run_cmd_test(
        name="create-project",
        cmd=f"zrb project create --project-dir {project_dir} --project {project_name}",
    )
    assert os.path.isfile(os.path.join(project_dir, "zrb_init.py"))
    # Create fastapp
    app_name = "fastapp"
    await run_cmd_test(
        name="create-fastapp",
        cmd=f"zrb project add fastapp --project-dir {project_dir} --app {app_name}",
    )
    assert os.path.isdir(os.path.join(project_dir, app_name))
    # Create module
    app_dir_path = os.path.join(project_dir, app_name)
    await run_cmd_test(
        name="create-module", cmd="zrb project fastapp create module --module library"
    )
    assert os.path.isdir(os.path.join(app_dir_path, "module", "library"))
    # Create entity
    await run_cmd_test(
        name="create-entity",
        cmd="zrb project fastapp create entity --module library --entity book --plural books --column title",  # noqa
    )
    assert os.path.isfile(os.path.join(app_dir_path, "schema", "book.py"))
    # Create migration
    await run_cmd_test(
        name="create-migration",
        cmd='zrb project fastapp create migration library --message "create book"',
    )
    # Start microservices
    await run_cmd_test(
        name="run-all",
        cmd="zrb project fastapp run all",
    )


remove_generated >> test_generate


# PLAYGROUND ==================================================================

playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    load_file(playground_zrb_init_path)

# GENERATED ===================================================================

generated_zrb_init_path = os.path.join(_DIR, "playground", "generated", "zrb_init.py")
if os.path.isfile(generated_zrb_init_path):
    load_file(generated_zrb_init_path)


async def run_cmd_test(name: str, cmd: CmdVal) -> Any:
    return await CmdTask(
        name=name,
        icon="🧪",
        color=WHITE,
        retries=0,
        env=Env("ZRB_SHOW_TIME", "False", link_to_os=False),
        cmd=cmd,
    ).async_run()
