import os

from zrb.builtin.group import searxng_group
from zrb.config.config import CFG
from zrb.input.int_input import IntInput
from zrb.task.cmd_task import CmdTask
from zrb.task.http_check import HttpCheck

start_searxng = searxng_group.add_task(
    CmdTask(
        name="start-searxng",
        input=IntInput(name="port", default=CFG.SEARXNG_PORT),
        cwd=os.path.dirname(__file__),
        cmd="docker run --rm -p {ctx.input.port}:8080 -v ./config/:/etc/searxng/ docker.io/searxng/searxng:latest -d",  # noqa
        readiness_check=HttpCheck(
            "check-searxng",
            url="http://localhost:{ctx.input.port}",
        ),
    ),
    alias="start",
)
