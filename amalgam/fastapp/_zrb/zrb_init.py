from zrb import Group, CmdTask, EnvFile, Env, EnvMap, Task, project_group
import os

_DIR = os.path.dirname(__file__)

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
            EnvFile(path=os.path.join(_DIR, "template.env")),
            Env(name="FASTAPP_APP_MODE", default="monolith"),
        ],
        cwd=_DIR,
        cmd='fastapi dev main.py --port "${FASTAPP_APP_PORT}"',
        auto_render_cmd=False,
        retries=0,
    ),
    alias="run"
)
run_microservices = app_microservices_group.add_task(
    Task(
        name="run-fastapp-as-microservices",
        description="▶️ Run Fastapp as a microservices",
    ),
    alias="run"
)


run_all = app_group.add_task(Task(name="run-all"))
run_all << [run_as_monolith, run_microservices]


run_gateway = app_group.add_task(CmdTask(
    name="run-gateway",
    env=[
        EnvFile(path=os.path.join(_DIR, "template.env")),
        EnvMap(vars={
            "FASTAPP_APP_MODE": "microservices",
            "FASTAPP_APP_PORT": "3001",
            "FASTAPP_APP_MODULES": "gateway",
            "FASTAPP_APP_LIBRARY_BASE_URL": "http://localhost:3002"
        }),
    ],
    cwd=_DIR,
    cmd='fastapi dev main.py --port "${FASTAPP_APP_PORT}"',
    auto_render_cmd=False,
    retries=0
))
run_gateway >> run_microservices


run_library = app_group.add_task(CmdTask(
    name="run-library",
    env=[
        EnvFile(path=os.path.join(_DIR, "template.env")),
        EnvMap(vars={
            "FASTAPP_APP_MODE": "microservices",
            "FASTAPP_APP_PORT": "3002",
            "FASTAPP_APP_MODULES": "library",
            "FASTAPP_APP_LIBRARY_BASE_URL": "http://localhost:3002"
        }),
    ],
    cwd=_DIR,
    cmd='fastapi dev main.py --port "${FASTAPP_APP_PORT}"',
    auto_render_cmd=False,
    retries=0
))
run_library >> run_microservices
