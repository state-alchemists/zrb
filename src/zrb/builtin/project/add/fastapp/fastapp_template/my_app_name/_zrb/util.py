import os
import platform

from my_app_name._zrb.config import APP_DIR

from zrb import AnyContext
from zrb.util.string.conversion import double_quote, to_snake_case


def run_my_app_name(ctx: AnyContext) -> str:
    subcommand = "dev" if ctx.input.env == "dev" else "run"
    return f'fastapi {subcommand}  main.py --port "${{MY_APP_NAME_PORT}}"'


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
