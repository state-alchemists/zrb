import os

from zrb import Cmd, CmdTask, EnvFile, EnvMap, Task, StrInput
from fastapp._zrb.config import (
    APP_DIR, MICROSERVICES_ENV_VARS, MONOLITH_ENV_VARS, ACTIVATE_VENV_SCRIPT
)


def create_migration(name: str, module: str) -> Task:
    return CmdTask(
        name=f"create-fastapp-{name}-migration",
        description=f"🧩 Create Fastapp {name.capitalize()} DB migration",
        input=StrInput(
            name="message",
            description="Migration message",
            prompt="Migration message",
            allow_empty=False,
        ),
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    "APP_DB_URL": f"sqlite:///{APP_DIR}/.migration.{module}.db",
                    "FASTAPP_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            f"cd {os.path.join(APP_DIR, 'module', module)}",
            "alembic upgrade head",
            Cmd(
                "alembic revision --autogenerate -m {double_quote(ctx.input.message)}",
                auto_render=True
            ),
        ],
        auto_render_cmd=False,
        retries=2,
    )


def migrate_module(name: str, module: str, as_microservices: bool) -> Task:
    env_vars = MICROSERVICES_ENV_VARS if as_microservices else MONOLITH_ENV_VARS
    return CmdTask(
        name=f"migrate-fastapp-{name}" if as_microservices else f"migrate-{name}-on-monolith",
        description=f"🧩 Run Fastapp {name.capitalize()} DB migration",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **env_vars,
                    "FASTAPP_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            f"cd {os.path.join(APP_DIR, 'module', module)}",
            "alembic upgrade head",
        ],
        auto_render_cmd=False,
        retries=2,
    )


def run_microservice(name: str, port: int, module: str) -> Task:
    return CmdTask(
        name=f"run-fastapp-{name}",
        description=f"🧩 Run Fastapp {name.capitalize()}",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **MICROSERVICES_ENV_VARS,
                    "FASTAPP_PORT": f"{port}",
                    "FASTAPP_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            'fastapi dev main.py --port "${FASTAPP_PORT}"',
        ],
        auto_render_cmd=False,
        retries=2,
    )
