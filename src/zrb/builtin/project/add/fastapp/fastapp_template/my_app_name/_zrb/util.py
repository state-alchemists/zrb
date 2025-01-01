import os
import platform

from my_app_name._zrb.config import (
    ACTIVATE_VENV_SCRIPT,
    APP_DIR,
    MICROSERVICES_ENV_VARS,
    MONOLITH_ENV_VARS,
)

from zrb import Cmd, CmdTask, EnvFile, EnvMap, StrInput, Task
from zrb.util.string.conversion import double_quote, to_snake_case


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


def migrate_module(name: str, module: str, as_microservices: bool) -> Task:
    env_vars = (
        dict(MICROSERVICES_ENV_VARS) if as_microservices else dict(MONOLITH_ENV_VARS)
    )
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


def run_microservice(name: str, port: int, module: str) -> Task:
    return CmdTask(
        name=f"run-my-app-name-{name}",
        description=f"🧩 Run My App Name {name.capitalize()}",
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


def set_create_migration_db_url_env(module_name: str) -> str:
    return set_env(
        "MY_APP_NAME_DB_URL",
        f"sqlite:///{APP_DIR}/.migration.{to_snake_case(module_name)}.db",
    )


def set_module_env(module_name: str) -> str:
    return (set_env("MY_APP_NAME_MODULES", to_snake_case(module_name)),)


def cd_module_script(module_name: str) -> str:
    module_dir_path = os.path.join(APP_DIR, "module", to_snake_case(module_name))
    return f"cd {module_dir_path}"


def set_env(var_name: str, var_value: str) -> str:
    """
    Generates a script to set an environment variable depending on the OS.
    :param var_name: Name of the environment variable.
    :param var_value: Value of the environment variable.
    :return: A string containing the appropriate script.
    """
    if platform.system() == "Windows":
        # PowerShell script for Windows
        script = f'[Environment]::SetEnvironmentVariable({double_quote(var_name)}, {double_quote(var_value)}, "User")'  # noqa
    else:
        # Bash script for Unix-like systems
        script = f"export {var_name}={double_quote(var_value)}"
    return script
