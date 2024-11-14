import os
import platform

from zrb import CmdTask, Env, EnvFile, EnvMap, Group, Task, project_group

APP_DIR = os.path.dirname(__file__)

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
prepare_venv >> run_as_monolith >> run_all

run_as_microservices = app_microservices_group.add_task(
    Task(
        name="run-app-name-as-microservices",
        description="🟢 Run App Name as microservices",
    ),
    alias="run",
)
prepare_venv >> run_as_microservices >> run_all

microservices_env_vars = {
    "APP_NAME_MODE": "microservices",
    "APP_NAME_AUTH_BASE_URL": "http://localhost:3002",
}

run_gateway = app_microservices_group.add_task(
    CmdTask(
        name="run-gateway",
        description="🟢 Run App Name Gateway",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **microservices_env_vars,
                    "APP_NAME_PORT": "3001",
                    "APP_NAME_MODULES": "gateway",
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
)
prepare_venv >> run_gateway >> run_as_microservices

run_auth = app_microservices_group.add_task(
    CmdTask(
        name="run-auth",
        description="🟢 Run App Name Auth",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **microservices_env_vars,
                    "APP_NAME_PORT": "3001",
                    "APP_NAME_MODULES": "auth",
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
)
prepare_venv >> run_auth >> run_as_microservices
