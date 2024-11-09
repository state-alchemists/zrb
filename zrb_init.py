from zrb import Task, CmdTask, CmdPath, TcpCheck, StrInput, Group, cli
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
    cwd=_DIR,
    cmd="./zrb-test.sh {ctx.input.test}",
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

prepare_and_run_test = Task(
    name="run-test",
    action=lambda ctx: ctx.xcom["run-integration-test"].pop_value(),
    cli_only=True
)
stop_test_docker_compose >> prepare_and_run_test

test_group.add_task(prepare_and_run_test, "run")

# FORMAT ============================================================================

cli.add_task(CmdTask(
    name="format-code",
    description="Format Zrb code",
    cwd=_DIR,
    cmd=CmdPath(os.path.join(_DIR, "zrb-format-code.sh"))
))

playground_zrb_init_path = os.path.join(_DIR, "playground", "zrb_init.py")
if os.path.isfile(playground_zrb_init_path):
    load_file(playground_zrb_init_path)

# Publish ===========================================================================


cli.add_task(CmdTask(
    name="publish",
    description="Publish Zrb",
    cwd=_DIR,
    cmd=CmdPath(os.path.join(_DIR, "zrb-publish.sh"))
))
