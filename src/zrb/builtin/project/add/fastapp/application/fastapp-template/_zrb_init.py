import os
import platform

from zrb import CmdTask, Env, EnvFile, EnvMap, Group, Task, project_group

APP_DIR = os.path.dirname(__file__)
APP_MODULE_NAME = os.path.basename(APP_DIR)

if platform.system() == "Windows":
    ACTIVATE_VENV_SCRIPT = "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser; . .venv\Scripts\Activate"  # noqa
else:
    ACTIVATE_VENV_SCRIPT = "source .venv/bin/activate"

create_venv = CmdTask(
    name="create-app-name-venv",
    cwd=APP_DIR,
    cmd="python -m venv .venv",
    execute_condition=lambda ctx: not os.path.isdir(os.path.join(APP_DIR, ".venv")),
)

prepare_venv = CmdTask(
    name="prepare-app-name-venv",
    cmd=[ACTIVATE_VENV_SCRIPT, "pip install -r requirements.txt"],
    cwd=APP_DIR,
)
create_venv >> prepare_venv

app_group = project_group.add_group(
    Group(name="app-name", description="🚀 Managing App Name")
)
app_monolith_group = app_group.add_group(
    Group(name="monolith", description="🏢 Managing App Name as monolith")
)
app_microservices_group = app_group.add_group(
    Group(name="microservices", description="🌐 Managing App Name as microservices")
)

run_all = app_group.add_task(
    Task(
        name="run-app-name", description="🟢 Run App Name as monolith and microservices"
    ),
    alias="run",
)

migrate_all = app_group.add_task(
    Task(name="migrate-app-name", description="📤 Run App Name migration"),
    alias="migrate",
)


migrate_monolith = app_monolith_group.add_task(
    CmdTask(
        name="run-app-name-migration",
        description="📤 Run App Name migration",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            Env(name="APP_NAME_MODE", default="monolith"),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            f"python -m {APP_MODULE_NAME}.migrate",
        ],
        auto_render_cmd=False,
        retries=0,
    ),
    alias="migrate",
)
prepare_venv >> migrate_monolith >> migrate_all

run_as_monolith = app_monolith_group.add_task(
    CmdTask(
        name="run-app-name-as-monolith",
        description="🟢 Run App Name as a monolith",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            Env(name="APP_NAME_MODE", default="monolith"),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            'fastapi dev main.py --port "${APP_NAME_PORT}"',
        ],
        auto_render_cmd=False,
        retries=0,
    ),
    alias="run",
)
migrate_monolith >> run_as_monolith >> run_all

migrate_microservices = app_microservices_group.add_task(
    Task(
        name="migrate-app-name-microservices", description="📤 Run App Name migration"
    ),
    alias="migrate",
)
migrate_microservices >> migrate_all

run_as_microservices = app_microservices_group.add_task(
    Task(
        name="run-app-name-as-microservices",
        description="🟢 Run App Name as microservices",
    ),
    alias="run",
)
run_as_microservices >> run_all


MICROSERVICES_ENV_VARS = {
    "APP_NAME_MODE": "microservices",
    "APP_NAME_AUTH_BASE_URL": "http://localhost:3002",
}


def migrate_microservice(name: str, module: str) -> Task:
    return CmdTask(
        name=f"migrate-{name}",
        description=f"📤 Run App Name {name.capitalize()} migration",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **MICROSERVICES_ENV_VARS,
                    "APP_NAME_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            f"python -m {APP_MODULE_NAME}.migrate",
        ],
        auto_render_cmd=False,
        retries=0,
    )


def run_microservice(name: str, port: int, module: str) -> Task:
    return CmdTask(
        name=f"run-{name}",
        description=f"🟢 Run App Name {name.capitalize()}",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **MICROSERVICES_ENV_VARS,
                    "APP_NAME_PORT": f"{port}",
                    "APP_NAME_MODULES": f"{module}",
                }
            ),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            'fastapi dev main.py --port "${APP_NAME_PORT}"',
        ],
        auto_render_cmd=False,
        retries=0,
    )


run_gateway = app_microservices_group.add_task(
    run_microservice("gateway", 3001, "gateway")
)
prepare_venv >> run_gateway >> run_as_microservices

migrate_auth = app_microservices_group.add_task(migrate_microservice("auth", "auth"))
prepare_venv >> migrate_auth >> migrate_microservices
run_auth = app_microservices_group.add_task(run_microservice("auth", 3002, "auth"))
migrate_auth >> run_auth >> run_as_microservices
