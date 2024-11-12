import os

from zrb import CmdTask, Env, EnvFile, EnvMap, Group, Task, project_group

_DIR = os.path.dirname(__file__)
_APP_DIR = os.path.dirname(_DIR)

app_group = project_group.add_group(
    Group(name="app-name", description="🚀 Managing App Name")
)
app_monolith_group = app_group.add_group(
    Group(name="monolith", description="🏢 Managing App Name as monolith")
)
app_microservices_group = app_group.add_group(
    Group(name="microservices", description="🌐 Managing App Name as microservices")
)

run_as_monolith = app_monolith_group.add_task(
    CmdTask(
        name="run-app-name-as-monolith",
        description="▶️ Run App Name as a monolith",
        env=[
            EnvFile(path=os.path.join(_APP_DIR, "template.env")),
            Env(name="FASTAPP_APP_MODE", default="monolith"),
        ],
        cwd=_APP_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_APP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    ),
    alias="run",
)

run_as_microservices = app_microservices_group.add_task(
    Task(
        name="run-app-name-as-microservices",
        description="▶️ Run App Name as microservices",
    ),
    alias="run",
)

run_all = app_group.add_task(
    Task(
        name="run-app-name", description="▶️ Run App Name as monolith and microservices"
    ),
    alias="run",
)
run_all << [run_as_monolith, run_as_microservices]


run_gateway = app_group.add_task(
    CmdTask(
        name="run-app-name-gateway",
        env=[
            EnvFile(path=os.path.join(_APP_DIR, "template.env")),
            EnvMap(
                vars={
                    "FASTAPP_APP_MODE": "microservices",
                    "FASTAPP_APP_PORT": "3001",
                    "FASTAPP_APP_MODULES": "gateway",
                    "FASTAPP_APP_LIBRARY_BASE_URL": "http://localhost:3002",
                }
            ),
        ],
        cwd=_APP_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_APP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    )
)
run_gateway >> run_as_microservices


run_library = app_group.add_task(
    CmdTask(
        name="run-app-name-library",
        env=[
            EnvFile(path=os.path.join(_APP_DIR, "template.env")),
            EnvMap(
                vars={
                    "FASTAPP_APP_MODE": "microservices",
                    "FASTAPP_APP_PORT": "3002",
                    "FASTAPP_APP_MODULES": "library",
                    "FASTAPP_APP_LIBRARY_BASE_URL": "http://localhost:3002",
                }
            ),
        ],
        cwd=_APP_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_APP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    )
)
run_library >> run_as_microservices
