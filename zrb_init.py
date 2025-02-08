import asyncio
import json
import os
import shutil
import traceback
from functools import partial
from typing import Any, Callable

import psutil
import requests
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
    Xcom,
    cli,
    make_task,
)
from zrb.builtin.git import git_commit
from zrb.config import DEFAULT_SHELL
from zrb.util.cli.style import stylize_green, stylize_magenta
from zrb.util.cmd.command import kill_pid, run_command
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
    ctx.print("Remove generated resources")
    shutil.rmtree(os.path.join(_DIR, "playground", "generated"))


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


@make_task(
    name="test-generated-app",
    description="🧪 Test generated app",
    group=test_generator_group,
    alias="validate",
    retries=0,
)
async def test_generated_fastapp(ctx: AnyContext) -> str:
    try:
        await asyncio.sleep(2)
        ctx.print(stylize_magenta("Test fastapp monolith"))
        await _test_fastapp_permission_api(ctx, "http://localhost:3000")
        await _test_fastapp_book_api(ctx, "http://localhost:3000")
        ctx.print(stylize_magenta("Test fastapp gateway"))
        await _test_fastapp_permission_api(ctx, "http://localhost:3001")
        await _test_fastapp_book_api(ctx, "http://localhost:3001")
        return "Test succeed, here have a beer 🍺"
    finally:
        app_pid_xcom: Xcom = ctx.xcom.get("run-generated-app-pid")
        app_pid = app_pid_xcom.pop()
        kill_pid(app_pid, print_method=ctx.print)
        print("\a")


remove_generated >> test_generate >> run_generated_fastapp >> test_generated_fastapp


async def _test_fastapp_permission_api(ctx: AnyContext, base_url: str):
    ctx.print(stylize_green("Test creating permission"))
    url = f"{base_url}/api/v1/permissions"
    json_data = json.dumps({"name": "admin", "description": "Can do everything"})
    ctx.print(url, json_data)
    response = requests.post(
        url, data=json_data, headers={"Content-Type": "application/json"}
    )
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json.get("name") == "admin"


async def _test_fastapp_book_api(ctx: AnyContext, base_url: str):
    ids = await _test_fastapp_book_api_bulk_insert(ctx, base_url)
    await _test_fastapp_book_api_bulk_update(ctx, base_url, ids)
    bleach_id = await _test_fastapp_book_api_get_with_filter(ctx, base_url)
    await _test_fastapp_book_api_update(ctx, base_url, id=bleach_id)
    naruto_id = await _test_fastapp_book_api_insert(ctx, base_url)
    await _test_fastapp_book_api_get_by_id(ctx, base_url, id=naruto_id)
    await _test_fastapp_book_api_get_without_filter(ctx, base_url)
    await _test_fastapp_book_api_delete(ctx, base_url, naruto_id)
    await _test_fastapp_book_api_bulk_delete(ctx, base_url, [bleach_id])


async def _test_fastapp_book_api_delete(ctx: AnyContext, base_url: str, id: str):
    ctx.print(stylize_green("Test delete book by id"))
    url = f"{base_url}/api/v1/books/{id}"
    ctx.print(url)
    response = requests.delete(url, headers={"Content-Type": "application/json"})
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200


async def _test_fastapp_book_api_bulk_delete(
    ctx: AnyContext, base_url: str, ids: list[str]
):
    ctx.print(stylize_green("Test delete books"))
    url = f"{base_url}/api/v1/books/bulk"
    json_data = json.dumps(ids)
    ctx.print(url, json_data)
    response = requests.delete(
        url, data=json_data, headers={"Content-Type": "application/json"}
    )
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200


async def _test_fastapp_book_api_get_by_id(
    ctx: AnyContext, base_url: str, id: str
) -> str:
    ctx.print(stylize_green("Test get book by id"))
    url = f"{base_url}/api/v1/books/{id}"
    ctx.print(url)
    response = requests.get(url, headers={"Content-Type": "application/json"})
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    book = response.json()
    assert book.get("title") == "Naruto"
    assert book.get("author") == "Masashi Kishimoto"
    assert book.get("isbn") == "978-0-1490-0625-5"


async def _test_fastapp_book_api_get_without_filter(
    ctx: AnyContext, base_url: str
) -> str:
    ctx.print(stylize_green("Test get books without filter"))
    url = f"{base_url}/api/v1/books"
    ctx.print(url)
    response = requests.get(url, headers={"Content-Type": "application/json"})
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    count = response_json.get("count")
    data = response_json.get("data")
    assert count == 5
    assert len(data) == 5


async def _test_fastapp_book_api_get_with_filter(ctx: AnyContext, base_url: str) -> str:
    ctx.print(stylize_green("Test get books with filter"))
    url = f"{base_url}/api/v1/books?filter=title:eq:Bleach"
    ctx.print(url)
    response = requests.get(url, headers={"Content-Type": "application/json"})
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    count = response_json.get("count")
    data = response_json.get("data")
    assert count == 1
    book = data[0]
    assert book.get("title") == "Bleach"
    assert book.get("author") == "Fujiko F. Fujio"
    assert book.get("isbn") == "978-8-1744-3763-1"
    return book.get("id")


async def _test_fastapp_book_api_bulk_insert(
    ctx: AnyContext, base_url: str
) -> list[str]:
    ctx.print(stylize_green("Test creating books"))
    url = f"{base_url}/api/v1/books/bulk"
    json_data = json.dumps(
        [
            {"title": "Doraemon", "isbn": "978-6-6625-3489-3", "author": "anonymous"},
            {"title": "P Man", "isbn": "978-0-9259-2124-6", "author": "anonymous"},
            {"title": "Kobochan", "isbn": "978-8-8818-0448-1", "author": "anonymous"},
            {"title": "Bleach", "isbn": "978-8-1744-3763-1", "author": "anonymous"},
        ]
    )
    ctx.print(url, json_data)
    response = requests.post(
        url, data=json_data, headers={"Content-Type": "application/json"}
    )
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 4
    isbns = [row.get("isbn") for row in response_json]
    assert "978-6-6625-3489-3" in isbns
    assert "978-0-9259-2124-6" in isbns
    assert "978-8-8818-0448-1" in isbns
    assert "978-8-1744-3763-1" in isbns
    titles = [row.get("title") for row in response_json]
    assert "Doraemon" in titles
    assert "P Man" in titles
    assert "Kobochan" in titles
    assert "Bleach" in titles
    authors = [row.get("author") for row in response_json]
    assert "anonymous" in authors
    return [row.get("id") for row in response_json]


async def _test_fastapp_book_api_bulk_update(
    ctx: AnyContext, base_url: str, ids: list[str]
):
    ctx.print(stylize_green("Test update books"))
    url = f"{base_url}/api/v1/books/bulk"
    json_data = json.dumps({"book_ids": ids, "data": {"author": "Fujiko F. Fujio"}})
    ctx.print(url, json_data)
    response = requests.put(
        url, data=json_data, headers={"Content-Type": "application/json"}
    )
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 4
    isbns = [row.get("isbn") for row in response_json]
    assert "978-6-6625-3489-3" in isbns
    assert "978-0-9259-2124-6" in isbns
    assert "978-8-8818-0448-1" in isbns
    assert "978-8-1744-3763-1" in isbns
    titles = [row.get("title") for row in response_json]
    assert "Doraemon" in titles
    assert "P Man" in titles
    assert "Kobochan" in titles
    assert "Bleach" in titles
    authors = [row.get("author") for row in response_json]
    assert "anonymous" not in authors
    assert "Fujiko F. Fujio" in authors


async def _test_fastapp_book_api_insert(ctx: AnyContext, base_url: str) -> str:
    ctx.print(stylize_green("Test creating a book"))
    url = f"{base_url}/api/v1/books"
    json_data = json.dumps(
        {"title": "Naruto", "isbn": "978-0-1490-0625-5", "author": "Masashi Kishimoto"},
    )
    ctx.print(url, json_data)
    response = requests.post(
        url, data=json_data, headers={"Content-Type": "application/json"}
    )
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json.get("title") == "Naruto"
    assert response_json.get("isbn") == "978-0-1490-0625-5"
    assert response_json.get("author") == "Masashi Kishimoto"
    return response_json.get("id")


async def _test_fastapp_book_api_update(ctx: AnyContext, base_url: str, id: str):
    ctx.print(stylize_green("Test update book"))
    url = f"{base_url}/api/v1/books/{id}"
    json_data = json.dumps({"author": "Tite Kubo"})
    ctx.print(url, json_data)
    response = requests.put(
        url, data=json_data, headers={"Content-Type": "application/json"}
    )
    ctx.print(response.status_code, response.text)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json.get("title") == "Bleach"
    assert response_json.get("isbn") == "978-8-1744-3763-1"
    assert response_json.get("author") == "Tite Kubo"


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
