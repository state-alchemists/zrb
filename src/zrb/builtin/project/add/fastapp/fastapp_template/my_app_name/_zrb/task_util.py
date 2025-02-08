import os

from my_app_name._zrb.config import (
    ACTIVATE_VENV_SCRIPT,
    APP_DIR,
    MICROSERVICES_ENV_VARS,
    MONOLITH_ENV_VARS,
)
from my_app_name._zrb.input import run_env_input
from my_app_name._zrb.util import (
    cd_module_script,
    run_my_app_name,
    set_create_migration_db_url_env,
    set_env,
    set_module_env,
)

from zrb import Cmd, CmdTask, EnvFile, EnvMap, StrInput, Task
from zrb.util.string.conversion import to_kebab_case, to_snake_case


def create_migration(module: str) -> Task:
    name = to_kebab_case(module)
    return CmdTask(
        name=f"create-my-app-name-{name}-migration",
        description=f"🧩 Create My App Name {name.capitalize()} DB migration",
        input=StrInput(
            name="message",
            description="Migration message",
            prompt="Migration message",
            allow_empty=False,
        ),
        env=EnvFile(path=os.path.join(APP_DIR, "template.env")),
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            set_create_migration_db_url_env(module),
            set_module_env(module),
            cd_module_script(module),
            "alembic upgrade head",
            Cmd(
                "alembic revision --autogenerate -m {double_quote(ctx.input.message)}",
                auto_render=True,
            ),
        ],
        render_cmd=False,
        retries=2,
    )


def migrate_module(
    module: str, as_microservices: bool, additional_env_vars: dict[str, str] = {}
) -> Task:
    name = to_kebab_case(module)
    env_vars = (
        dict(MICROSERVICES_ENV_VARS) if as_microservices else dict(MONOLITH_ENV_VARS)
    )
    env_vars.update(additional_env_vars)
    if as_microservices:
        env_vars["MY_APP_NAME_MODULES"] = to_snake_case(module)
    return CmdTask(
        name=(
            f"migrate-my-app-name-{name}"
            if as_microservices
            else f"migrate-{name}-on-monolith"
        ),
        description=f"🧩 Run My App Name {name.capitalize()} DB migration",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(vars=env_vars),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            cd_module_script(module),
            "alembic upgrade head",
        ],
        render_cmd=False,
        retries=2,
    )


def run_microservice(module: str, port: int) -> Task:
    name = to_kebab_case(module)
    return CmdTask(
        name=f"run-my-app-name-{name}",
        description=f"🧩 Run My App Name {name.capitalize()}",
        input=run_env_input,
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **MICROSERVICES_ENV_VARS,
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            set_env("MY_APP_NAME_MODULES", module),
            set_env("MY_APP_NAME_PORT", f"{port}"),
            run_my_app_name,
        ],
        render_cmd=False,
        retries=2,
    )
