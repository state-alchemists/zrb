import os
import secrets
import shutil

from zrb.builtin.group import searxng_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.task.cmd_task import CmdTask
from zrb.task.http_check import HttpCheck
from zrb.task.make_task import make_task


@make_task(
    name="copy-searxng-setting",
)
def copy_searxng_setting(ctx: AnyContext):
    # Docker mounts ./.config/searxng/ as /etc/searxng/, so settings.yml must live there.
    dest_config_dir = os.path.abspath(
        os.path.join(os.path.expanduser("~"), ".config", "searxng")
    )
    os.makedirs(dest_config_dir, exist_ok=True)

    dest_config_file = os.path.join(dest_config_dir, "settings.yml")
    if not os.path.isfile(dest_config_file):
        ctx.print(f"Creating Searxng config file")
        src_config_file = os.path.join(
            os.path.dirname(__file__), "config", "settings.yml.new"
        )
        with open(src_config_file, "r") as f:
            content = f.read()
        secret_key = secrets.token_hex(32)
        content = content.replace('"ultrasecretkey"', f'"{secret_key}"')
        with open(dest_config_file, "w") as f:
            f.write(content)
        ctx.print(f"Searxng config file created: {dest_config_file}")

    dest_limiter_file = os.path.join(dest_config_dir, "limiter.toml")
    if not os.path.isfile(dest_limiter_file):
        src_limiter_file = os.path.join(
            os.path.dirname(__file__), "config", "limiter.toml"
        )
        shutil.copy(src_limiter_file, dest_limiter_file)


start_searxng = searxng_group.add_task(
    CmdTask(
        name="start-searxng",
        input=IntInput(name="port", default=CFG.SEARXNG_PORT),
        upstream=copy_searxng_setting,
        cwd=os.path.expanduser("~"),
        cmd="docker run --rm -p {ctx.input.port}:8080 -e SEARXNG_LIMITER=false -v ./.config/searxng/:/etc/searxng/ docker.io/searxng/searxng:2026.5.6-36bcd6b55 -d",  # noqa
        readiness_check=HttpCheck(
            "check-searxng",
            url="http://localhost:{ctx.input.port}",
        ),
    ),
    alias="start",
)
