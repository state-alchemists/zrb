import os

from zrb import CmdTask, Env, EnvFile, EnvMap, Group, Task, project_group

_DIR = os.path.dirname(__file__)
_APP_DIR = os.path.dirname(_DIR)

app_group = project_group.add_group(
    Group(name="fastapp", description="🚀 Managing Fastapp")
)
app_monolith_group = app_group.add_group(
    Group(name="monolith", description="🏢 Managing Fastapp as monolith")
)
app_microservices_group = app_group.add_group(
    Group(name="microservices", description="🌐 Managing Fastapp as microservices")
)

run_as_monolith = app_monolith_group.add_task(
    CmdTask(
        name="run-fastapp-as-monolith",
        description="▶️ Run Fastapp as a monolith",
        env=[
            EnvFile(path=os.path.join(_APP_DIR, "template.env")),
            Env(name="FASTAPP_MODE", default="monolith"),
        ],
        cwd=_APP_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    ),
    alias="run",
)

run_as_microservices = app_microservices_group.add_task(
    Task(
        name="run-fastapp-as-microservices",
        description="▶️ Run Fastapp as microservices",
    ),
    alias="run",
)

run_all = app_group.add_task(
    Task(
        name="run-fastapp", description="▶️ Run Fastapp as monolith and microservices"
    ),
    alias="run",
)
run_all << [run_as_monolith, run_as_microservices]


run_gateway = app_group.add_task(
    CmdTask(
        name="run-fastapp-gateway",
        env=[
            EnvFile(path=os.path.join(_APP_DIR, "template.env")),
            EnvMap(
                vars={
                    "FASTAPP_MODE": "microservices",
                    "FASTAPP_PORT": "3001",
                    "FASTAPP_MODULES": "gateway",
                    "FASTAPP_LIBRARY_BASE_URL": "http://localhost:3002",
                }
            ),
        ],
        cwd=_APP_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    )
)
run_gateway >> run_as_microservices


run_library = app_group.add_task(
    CmdTask(
        name="run-fastapp-library",
        env=[
            EnvFile(path=os.path.join(_APP_DIR, "template.env")),
            EnvMap(
                vars={
                    "FASTAPP_MODE": "microservices",
                    "FASTAPP_PORT": "3002",
                    "FASTAPP_MODULES": "library",
                    "FASTAPP_LIBRARY_BASE_URL": "http://localhost:3002",
                }
            ),
        ],
        cwd=_APP_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    )
)
run_library >> run_as_microservices
