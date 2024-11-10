from zrb import Task, CmdTask, CmdPath, Env, TcpCheck, StrInput, Group, cli
from zrb.util.load import load_file
import os

_DIR = os.path.dirname(__file__)

# TEST ==============================================================================

test_group = cli.add_group(Group("test", description="Testing zrb"))

clean_up_resources = CmdTask(
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
clean_up_resources >> start_test_docker_compose

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

code_group = cli.add_group(Group("code", description="Code related command"))

format_code = code_group.add_task(
    CmdTask(
        name="format-code",
        description="Format Zrb code",
        cwd=_DIR,
        cmd=CmdPath(os.path.join(_DIR, "zrb-format-code.sh"))
    ),
    alias="format"
)


# GIT ===============================================================================

git_group = cli.add_group(Group("git", description="git related command"))

push_git = git_group.add_task(
    CmdTask(
        name="push-git",
        input=StrInput(
            name="message",
            description="Commit message",
            prompt="Commit message (i.e., Adding some new feature, Fixing some bug)",
            default_str="Adding some new feature",
        ),
        description="Push Zrb code",
        cwd=_DIR,
        cmd=[
            "git add . -A",
            "git commit -m '{ctx.input.message}'",
            "git push -u origin HEAD",
        ]
    ),
    alias="push"
)
format_code >> push_git


# PIP ================================================================================

pip_group = cli.add_group(Group("pip", description="Pip related command"))

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

# PLAYGROUND ========================================================================

playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    load_file(playground_zrb_init_path)
