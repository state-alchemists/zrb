import os

from fastapp._zrb.config import ACTIVATE_VENV_SCRIPT, APP_DIR
from fastapp._zrb.group import (
    app_create_group,
    app_migrate_group,
    app_run_group,
)
from fastapp._zrb.helper import (
    create_migration,
    migrate_module,
    run_microservice,
)
from fastapp._zrb.venv_task import prepare_venv

from zrb import CmdTask, Env, EnvFile, Task

# 🚀 Run/Migrate All ===========================================================

run_all = app_run_group.add_task(
    Task(
        name="run-fastapp", description="🟢 Run Fastapp as monolith and microservices"
    ),
    alias="all",
)

migrate_all = app_migrate_group.add_task(
    Task(
        name="migrate-fastapp",
        description="📦 Run Fastapp DB migration for monolith and microservices",
    ),
    alias="all",
)

create_all_migration = app_create_group.add_task(
    Task(
        name="create-fastapp-migration", description="📦 Create Fastapp DB migration"
    ),
    alias="migration",
)

# 🗿 Run/Migrate Monolith =====================================================

run_monolith = app_run_group.add_task(
    CmdTask(
        name="run-monolith-fastapp",
        description="🗿 Run Fastapp as a monolith",
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
        retries=2,
    ),
    alias="monolith",
)
prepare_venv >> run_monolith >> run_all

migrate_monolith = app_migrate_group.add_task(
    Task(
        name="migrate-monolith-fastapp",
        description="🗿 Run Fastapp DB migration for monolith",
    ),
    alias="monolith",
)
migrate_monolith >> migrate_all

# 🌐 Run/Migrate Microsevices ==================================================

run_microservices = app_run_group.add_task(
    Task(
        name="run-microservices-fastapp",
        description="🌐 Run Fastapp as microservices",
    ),
    alias="microservices",
)
run_microservices >> run_all

migrate_microservices = app_migrate_group.add_task(
    Task(
        name="migrate-microservices-fastapp",
        description="🌐 Run Fastapp DB migration for microservices",
    ),
    alias="microservices",
)
migrate_microservices >> migrate_all

# 📡 Run/Migrate Gateway =======================================================

run_gateway = app_run_group.add_task(
    run_microservice("gateway", 3001, "gateway"), alias="microservices-gateway"
)
prepare_venv >> run_gateway >> run_microservices

create_gateway_migration = app_create_group.add_task(
    create_migration("gateway", "gateway"), alias="gateway-migration"
)
prepare_venv >> create_gateway_migration >> create_all_migration

migrate_monolith_gateway = migrate_module("gateway", "gateway", as_microservices=False)
prepare_venv >> migrate_monolith_gateway >> [migrate_monolith, run_monolith]

migrate_microservices_gateway = app_migrate_group.add_task(
    migrate_module("gateway", "gateway", as_microservices=True),
    alias="microservices-gateway",
)
prepare_venv >> migrate_microservices_gateway >> [migrate_microservices, run_gateway]

# 🔐 Run/Migrate Auth ==========================================================

run_auth = app_run_group.add_task(
    run_microservice("auth", 3002, "auth"), alias="microservices-auth"
)
prepare_venv >> run_auth >> run_microservices

create_auth_migration = app_create_group.add_task(
    create_migration("auth", "auth"), alias="auth-migration"
)
prepare_venv >> create_auth_migration >> create_all_migration

migrate_monolith_auth = migrate_module("auth", "auth", as_microservices=False)
prepare_venv >> migrate_monolith_auth >> [migrate_monolith, run_monolith]

migrate_microservices_auth = app_migrate_group.add_task(
    migrate_module("auth", "auth", as_microservices=True), alias="microservices-auth"
)
prepare_venv >> migrate_microservices_auth >> [migrate_microservices, run_auth]
