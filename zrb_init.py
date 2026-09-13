import json
import os
import tomllib
from urllib.parse import urlparse

import requests

from zrb import (
    AnyContext,
    CmdPath,
    CmdTask,
    Env,
    Group,
    LLMTask,
    StrInput,
    Task,
    TcpCheck,
    Tpl,
    cli,
    make_task,
)
from zrb.builtin.git import git_commit
from zrb.llm.tool import read_file as read_file_tool
from zrb.llm.tool import run_shell_command as run_shell_command_tool
from zrb.util.file import read_file

_DIR = os.path.dirname(__file__)

# stdlib `tomllib`, not `tomlkit`: this file is loaded by the `zrb` inside the
# CI container, which installs `--without dev`. It resolves there today only
# because the image happens to `pip install poetry`, which drags tomlkit into
# the same site-packages -- and ZRB_INIT_STRICT makes that accident fatal.
_PYPROJECT = tomllib.loads(read_file(os.path.join(_DIR, "pyproject.toml")))
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
    env=Env(name="TEST", default=Tpl("{ctx.input.test}"), link_to_os=False),
    cwd=_DIR,
    cmd=CmdPath(os.path.join(_DIR, "zrb-test.sh")),
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

git_diff = CmdTask(
    name="git-diff",
    input=StrInput(
        name="range",
        description="Git range to review (e.g. origin/main...HEAD)",
        prompt="Git range",
        default="origin/main...HEAD",
    ),
    cmd=Tpl('git diff --stat "{ctx.input.range}"'),
)

review_code = code_group.add_task(
    LLMTask(
        name="review-code",
        description="🔍 Review changed code with the LLM reviewer",
        input=[
            StrInput(
                name="range",
                description="Git range to review (e.g. origin/main...HEAD)",
                prompt="Git range",
                default="origin/main...HEAD",
            ),
        ],
        tools=[read_file_tool, run_shell_command_tool],
        message=Tpl(
            "Review the changes in git range {ctx.input.range}."
            " Changed files: {ctx.xcom.git_diff.peek()}"
            " Read the diff with git and read the files it touches."
            " Report ALL defects you can point at in the diff:"
            " a wrong result, a crash, a leak, a security hole."
            " Skip style and speculation."
            " Do NOT run the test suite, build, or any linter --"
            " CI already ran them in a separate step and a second run"
            " here only burns minutes."
            " Work directly: no skill activation, no delegation,"
            " no plan -- go straight to reading the diff."
            " Your review should be in markdown format"
            " Give every finding its own section with"
            " Problem, Location (file:line) and Suggestion, and end the"
            " report with a verdict line reading either"
            " 'Request changes' or 'LGTM'."
            ' Then print that verdict as a single line."'
        ),
    ),
    alias="review",
)


@make_task(
    name="submit-comment",
    description="💬 Post code review comment",
    retries=2,
    group=cli,
)
def submit_comment(ctx: AnyContext):
    """Post `--file` as a comment on the PR that triggered this run.

    The PR number is read from GITHUB_EVENT_PATH -- the event payload GitHub
    writes for every run -- rather than passed in from a workflow `${{ }}`
    interpolation, so the task takes no argument but the file and works from
    any workflow that sets the standard GitHub Actions variables.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    missing = [
        name
        for name, value in (
            ("GITHUB_TOKEN", token),
            ("GITHUB_EVENT_PATH", event_path),
            ("GITHUB_REPOSITORY", repository),
        )
        if value == ""
    ]
    if missing:
        raise ValueError(
            f"Not running inside GitHub Actions? Missing: {', '.join(missing)}"
        )
    body: str = ctx.xcom.review_code.peek()
    pr_number = json.loads(read_file(event_path)).get("pull_request", {}).get("number")
    if pr_number is None:
        raise ValueError("The event payload carries no pull_request.number")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if urlparse(api_url).hostname != "api.github.com":
        raise ValueError(f"Refusing to send GITHUB_TOKEN to {api_url}")
    response = requests.post(
        f"{api_url}/repos/{repository}/issues/{pr_number}/comments",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"body": body},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"Could not comment on PR #{pr_number}: "
            f"{response.status_code} {response.text}"
        )
    ctx.print(f"Posted {len(body)} bytes to PR #{pr_number}")


_ = git_diff >> review_code >> submit_comment

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
