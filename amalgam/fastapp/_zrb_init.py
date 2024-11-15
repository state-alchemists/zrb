import os
import platform

from zrb import CmdTask, Env, EnvFile, EnvMap, Group, Task, project_group

APP_DIR = os.path.dirname(__file__)

if platform.system() == "Windows":
    ACTIVATE_VENV_SCRIPT = "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser; . .venv\Scripts\Activate"  # noqa
else:
    ACTIVATE_VENV_SCRIPT = "source .venv/bin/activate"

create_venv = CmdTask(
    name="create-fastapp-venv",
    cwd=APP_DIR,
    cmd="python -m venv .venv",
    execute_condition=lambda ctx: not os.path.isdir(os.path.join(APP_DIR, ".venv")),
)

prepare_venv = CmdTask(
    name="prepare-fastapp-venv",
    cmd=[ACTIVATE_VENV_SCRIPT, "pip install -r requirements.txt"],
    cwd=APP_DIR,
)
create_venv >> prepare_venv

app_group = project_group.add_group(
    Group(name="fastapp", description="🚀 Managing Fastapp")
)
app_monolith_group = app_group.add_group(
    Group(name="monolith", description="🏢 Managing Fastapp as monolith")
)
app_microservices_group = app_group.add_group(
    Group(name="microservices", description="🌐 Managing Fastapp as microservices")
)

run_all = app_group.add_task(
    Task(
        name="run-fastapp", description="🟢 Run Fastapp as monolith and microservices"
    ),
    alias="run",
)

run_as_monolith = app_monolith_group.add_task(
    CmdTask(
        name="run-fastapp-as-monolith",
        description="🟢 Run Fastapp as a monolith",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            Env(name="FASTAPP_MODE", default="monolith"),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            'fastapi dev main.py --port "${FASTAPP_PORT}"',
        ],
        auto_render_cmd=False,
        retries=0,
    ),
    alias="run",
)
prepare_venv >> run_as_monolith >> run_all

run_as_microservices = app_microservices_group.add_task(
    Task(
        name="run-fastapp-as-microservices",
        description="🟢 Run Fastapp as microservices",
    ),
    alias="run",
)
run_as_microservices >> run_all


def run_microservices(name: str, port: int, module: str) -> Task:
    microservices_env_vars = {
        "FASTAPP_MODE": "microservices",
        "FASTAPP_AUTH_BASE_URL": "http://localhost:3002",
    }
    return CmdTask(
        name=f"run-{name}",
        description="🟢 Run Fastapp {name.capitalize()}",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            EnvMap(
                vars={
                    **microservices_env_vars,
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
        retries=0,
    )


run_gateway = app_microservices_group.add_task(
    run_microservices("gateway", 3001, "gateway")
)
prepare_venv >> run_gateway >> run_as_microservices
run_auth = app_microservices_group.add_task(run_microservices("auth", 3002, "auth"))
prepare_venv >> run_auth >> run_as_microservices
