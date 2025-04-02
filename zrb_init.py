import os
import shutil
import traceback
from functools import partial
from typing import Any

import tomlkit

from zrb import (
    AnyContext,
    CmdPath,
    CmdTask,
    Env,
    Group,
    HttpCheck,
    StrInput,
    Task,
    TcpCheck,
    cli,
    make_task,
)
from zrb.builtin.git import git_commit
from zrb.config import DEFAULT_SHELL
from zrb.util.cmd.command import run_command
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
        allow_empty=True,
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
        description="🧪 Run Test",
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
            "isort . --profile black --force-grid-wrap 0",
            "black .",
        ],
    ),
    alias="format",
)
format_code >> git_commit

# DOCKER ======================================================================

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

# PUBLISH =====================================================================

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
    Task(name="publish-all", description="Publish Zrb"), alias="all"
)
publish_all << [publish_pip, publish_docker]

# GENERATOR TEST =============================================================

test_generator_group = test_group.add_group(
    Group("generator", description="🔥 Testing generator")
)


@make_task(
    name="remove-generated",
    description="🔄 Remove generated resources",
)
async def remove_generated(ctx: AnyContext):
    generated_dir = os.path.join(_DIR, "playground", "generated")
    if os.path.exists(generated_dir):
        ctx.print("Remove generated resources")
        shutil.rmtree(generated_dir)


@make_task(
    name="test-generate",
    description="🪄 Generate app",
    group=test_generator_group,
    alias="scaffold",
    retries=0,
)
async def test_generate(ctx: AnyContext):
    # Create project
    project_dir = os.path.join(_DIR, "playground", "generated")
    project_name = "Amalgam"

    ctx.print("Generate project")
    await _run_shell_script(
        ctx, f"zrb project create --project-dir {project_dir} --project {project_name}"
    )
    assert os.path.isfile(os.path.join(project_dir, "zrb_init.py"))
    # Create fastapp
    app_name = "fastapp"
    ctx.print("Generate fastapp")
    await _run_shell_script(
        ctx, f"zrb project add fastapp --project-dir {project_dir} --app {app_name}"
    )
    assert os.path.isdir(os.path.join(project_dir, app_name))
    # Create module
    app_dir_path = os.path.join(project_dir, app_name)
    ctx.print("Generate module")
    await _run_shell_script(ctx, "zrb project fastapp create module --module library")
    assert os.path.isdir(os.path.join(app_dir_path, "module", "library"))
    # Create entity
    ctx.print("Generate entity")
    await _run_shell_script(
        ctx,
        "zrb project fastapp create entity --module library --entity book --plural books --column isbn",  # noqa
    )
    assert os.path.isfile(os.path.join(app_dir_path, "schema", "book.py"))
    # Create column
    ctx.print("Generate column")
    await _run_shell_script(
        ctx,
        "zrb project fastapp create column --module library --entity book --column title --type str",  # noqa
    )
    await _run_shell_script(
        ctx,
        "zrb project fastapp create column --module library --entity book --column author --type str",  # noqa
    )
    # Create migration
    ctx.print("Generate migration")
    await _run_shell_script(
        ctx, 'zrb project fastapp create migration library --message "test migration"'
    )


run_generated_fastapp = test_generator_group.add_task(
    CmdTask(
        name="run-generated-app",
        description="🏃 Run generated app",
        readiness_check=[
            HttpCheck(name="check-monolith", url="http://localhost:3000/readiness"),
            HttpCheck(name="check-gateway", url="http://localhost:3001/readiness"),
            HttpCheck(name="check-auth-svc", url="http://localhost:3002/readiness"),
            HttpCheck(name="check-lib-svc", url="http://localhost:3003/readiness"),
        ],
        cmd="FASTAPP_AUTH_SUPER_USER_PASSWORD=admin zrb project fastapp run all --env prod",
        plain_print=True,
        retries=0,
    ),
    alias="launch",
)


test_generated_fastapp = test_generator_group.add_task(
    CmdTask(
        name="test-generated-app",
        description="🧪 Test generated app",
        cmd="zrb project fastapp test",
        plain_print=True,
        retries=0,
    ),
    alias="validate",
)

remove_generated >> test_generate >> [run_generated_fastapp, test_generated_fastapp]


# PLAYGROUND ==================================================================

playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    try:
        load_file(playground_zrb_init_path)
    except Exception:
        traceback.print_exc()

# GENERATED ===================================================================

generated_zrb_init_path = os.path.join(_DIR, "playground", "generated", "zrb_init.py")
if os.path.isfile(generated_zrb_init_path):
    try:
        load_file(generated_zrb_init_path)
    except Exception:
        traceback.print_exc()


async def _run_shell_script(ctx: AnyContext, script: str) -> Any:
    shell = DEFAULT_SHELL
    flag = "/c" if shell.lower() == "powershell" else "-c"
    cmd_result, return_code = await run_command(
        cmd=[shell, flag, script],
        cwd=_DIR,
        print_method=partial(ctx.print, plain=True),
    )
    if return_code != 0:
        ctx.log_error(f"Exit status: {return_code}")
        raise Exception(f"Process exited ({return_code}): {cmd_result.error}")
    return cmd_result
