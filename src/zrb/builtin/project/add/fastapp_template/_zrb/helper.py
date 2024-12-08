import os

from fastapp_template._zrb.config import (
    ACTIVATE_VENV_SCRIPT,
    APP_DIR,
    MICROSERVICES_ENV_VARS,
    MONOLITH_ENV_VARS,
)

from zrb import Cmd, CmdTask, EnvFile, EnvMap, StrInput, Task


def create_migration(name: str, module: str) -> Task:
    return CmdTask(
        name=f"create-my-app-name-{name}-migration",
        description=f"🧩 Create My App Name {name.capitalize()} DB migration",
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
                    "MY_APP_NAME_MODULES": f"{module}",
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
                auto_render=True,
            ),
        ],
        render_cmd=False,
        retries=2,
    )


def migrate_module(name: str, module: str, as_microservices: bool) -> Task:
    env_vars = MICROSERVICES_ENV_VARS if as_microservices else MONOLITH_ENV_VARS
    return CmdTask(
        name=(
            f"migrate-my-app-name-{name}"
            if as_microservices
            else f"migrate-{name}-on-monolith"
        ),
        description=f"🧩 Run My App Name {name.capitalize()} DB migration",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **env_vars,
                    "MY_APP_NAME_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            f"cd {os.path.join(APP_DIR, 'module', module)}",
            "alembic upgrade head",
        ],
        render_cmd=False,
        retries=2,
    )


def run_microservice(name: str, port: int, module: str) -> Task:
    return CmdTask(
        name=f"run-my-app-name-{name}",
        description=f"🧩 Run My App Name {name.capitalize()}",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **MICROSERVICES_ENV_VARS,
                    "MY_APP_NAME_PORT": f"{port}",
                    "MY_APP_NAME_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            'fastapi dev main.py --port "${MY_APP_NAME_PORT}"',
        ],
        render_cmd=False,
        retries=2,
    )


def get_existing_module_names() -> list[str]:
    module_dir_path = os.path.join(APP_DIR, "module")
    return [entry.name for entry in os.scandir(module_dir_path) if entry.is_dir()]


def get_existing_schema_names() -> list[str]:
    module_dir_path = os.path.join(APP_DIR, "schema")
    return [
        os.path.splitext(entry.name)[0]
        for entry in os.scandir(module_dir_path)
        if entry.is_file() and entry.name.endswith(".py")
    ]
