from zrb import Task, CmdTask, TcpCheck, StrInput, Group, cli
from zrb.util.load import load_file
import os

_DIR = os.path.dirname(__file__)


test_group = cli.add_group(Group("test", description="Testing zrb"))

_clean_up_resources = CmdTask(
    name="clean-up-resources",
    cwd=os.path.join(_DIR, "test"),
    cmd=[
        "sudo -k rm -Rf task/scaffolder/test-generated"
    ]
)

_start_test_docker_compose = CmdTask(
    name="start-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down && docker compose up",
    readiness_check=TcpCheck(
        name="check-start-test-compose",
        port=2222
    )
)
_clean_up_resources >> _start_test_docker_compose

_run_integration_test = CmdTask(
    name="run-integration-test",
    input=StrInput(
        name="test",
        description="Specific test case (i.e., test/file.py::test_name)",
        prompt="Test (i.e., test/file.py::test_name)",
        default_str="",
    ),
    cwd=_DIR,
    cmd="./test.sh {ctx.input.test}",
    retries=0,
)
_start_test_docker_compose >> _run_integration_test

_stop_test_docker_compose = CmdTask(
    name="stop-test-compose",
    description="Start docker compose for testing, run test, then remove the docker compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down"
)
_run_integration_test >> _stop_test_docker_compose

run_test = Task(
    name="run-test",
    action=lambda ctx: ctx.xcom["run-integration-test"].pop_value(),
    cli_only=True
)
_stop_test_docker_compose >> run_test

test_group.add_task(run_test, "run")


playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    load_file(playground_zrb_init_path)
