import os

import tomlkit

from zrb import (
    CmdPath,
    CmdTask,
    Env,
    Group,
    StrInput,
    Task,
    TcpCheck,
    cli,
)
from zrb.builtin.git import git_commit
from zrb.util.file import read_file

_DIR = os.path.dirname(__file__)

_PYPROJECT = tomlkit.loads(read_file(os.path.join(_DIR, "pyproject.toml")))
_VERSION = _PYPROJECT["project"]["version"]


# TEST =======================================================================

test_group = cli.add_group(Group("test", description="🔍 Testing zrb codebase"))

clean_up_test_resources = CmdTask(
    name="clean-up-resources",
    cwd=os.path.join(_DIR, "test"),
    cmd=["sudo -k rm -Rf task/scaffolder/generated"],
    is_interactive=True,
)

start_test_docker_compose = CmdTask(
    name="start-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down && docker compose up",
    readiness_check=TcpCheck(name="check-start-test-compose", port=2222),
)
_ = clean_up_test_resources >> start_test_docker_compose

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
_ = start_test_docker_compose >> run_test

stop_test_docker_compose = CmdTask(
    name="stop-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down",
)
_ = run_test >> stop_test_docker_compose

prepare_and_run_test = test_group.add_task(
    Task(
        name="run-test",
        description="🧪 Run Test",
        action=lambda ctx: ctx.xcom["run-integration-test"].pop(),
        cli_only=True,
    ),
    alias="run",
)
_ = stop_test_docker_compose >> prepare_and_run_test


# CODE ========================================================================

code_group = cli.add_group(Group("code", description="📜 Code related command"))

format_code = code_group.add_task(
    CmdTask(
        name="format-code",
        description="Format Zrb code",
        cwd=_DIR,
        cmd=[
            "isort . --profile black --force-grid-wrap 0 --skip-glob 'llm-challenges/**'",
            "black . --extend-exclude 'llm-challenges'",
        ],
    ),
    alias="format",
)
_ = format_code >> git_commit

# DOCKER ======================================================================

docker_group = cli.add_group(
    Group(name="docker", description="🐋 Docker related command")
)
docker_build_group = docker_group.add_group(
    Group(name="build", description="Build images")
)
docker_publish_group = docker_group.add_group(
    Group(name="publish", description="Publish images")
)

build_normal_docker_image = docker_build_group.add_task(
    CmdTask(
        name="build-zrb-normal-docker-image",
        description="Build Zrb normal docker image",
        cwd=_DIR,
        cmd=f"docker build . --target normal -t stalchmst/zrb:{_VERSION} -t stalchmst/zrb:latest",  # noqa
    ),
    alias="normal",
)
_ = format_code >> build_normal_docker_image

build_dind_docker_image = docker_build_group.add_task(
    CmdTask(
        name="build-zrb-dind-docker-image",
        description="Build Zrb dind docker image",
        cwd=_DIR,
        cmd=f"docker build . --target dind -t stalchmst/zrb:{_VERSION}-dind -t stalchmst/zrb:latest-dind",  # noqa
    ),
    alias="dind",
)
_ = build_normal_docker_image >> build_dind_docker_image

build_docker_image = docker_build_group.add_task(
    Task(name="build-zrb-docker-images"),
    alias="all",
)
_ = build_docker_image << [build_dind_docker_image, build_normal_docker_image]

publish_normal_docker_image = docker_publish_group.add_task(
    CmdTask(
        name="publish-zrb-normal-docker-image",
        description="Publish Zrb normal docker image",
        cwd=_DIR,
        cmd=[
            "docker push stalchmst/zrb:latest",
            f"docker push stalchmst/zrb:{_VERSION}",
        ],
    ),
    alias="normal",
)
_ = build_normal_docker_image >> publish_normal_docker_image

publish_dind_docker_image = docker_publish_group.add_task(
    CmdTask(
        name="publish-zrb-dind-docker-image",
        description="Publish Zrb dind docker image",
        cwd=_DIR,
        cmd=[
            "docker push stalchmst/zrb:latest-dind",
            f"docker push stalchmst/zrb:{_VERSION}-dind",
        ],
    ),
    alias="dind",
)
_ = publish_dind_docker_image << [build_dind_docker_image, publish_normal_docker_image]

publish_docker_image = docker_publish_group.add_task(
    Task(name="publish-zrb-docker-images"),
    alias="all",
)
_ = publish_docker_image << [publish_normal_docker_image, publish_dind_docker_image]


# PUBLISH =====================================================================

publish_group = cli.add_group(
    Group(name="publish", description="📦 Publication related command")
)

publish_code = publish_group.add_task(
    CmdTask(
        name="publish-zrb-code",
        description="Publish Zrb code",
        cwd=_DIR,
        cmd=[f"git tag -a {_VERSION} -m {_VERSION}", f"git push -u origin {_VERSION}"],
    ),
    alias="code",
)
_ = format_code >> publish_code

publish_pip = publish_group.add_task(
    CmdTask(
        name="publish-zrb-to-pip",
        description="Publish Zrb as pip package",
        cwd=_DIR,
        # build_pypi_readme.py generates README.pypi.md (the file Poetry packages)
        # by rewriting README.md's relative `docs/X` links to absolute,
        # version-tagged GitHub URLs. Run before every publish so PyPI gets
        # links that point to the matching release's docs.
        cmd=(
            "rm -Rf dist"
            " && python scripts/build_pypi_readme.py"
            " && poetry publish --build --skip-existing"
        ),
    ),
    alias="pip",
)
_ = format_code >> publish_pip

publish_group.add_task(publish_docker_image, alias="docker")

publish_all = publish_group.add_task(
    Task(name="publish-all", description="Publish Zrb"), alias="all"
)
_ = publish_all << [publish_pip, publish_docker_image, publish_code]
