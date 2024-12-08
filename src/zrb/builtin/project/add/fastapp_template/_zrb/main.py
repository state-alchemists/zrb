import os

from fastapp_template._zrb.column.create_column_task import create_my_app_name_column
from fastapp_template._zrb.config import ACTIVATE_VENV_SCRIPT, APP_DIR
from fastapp_template._zrb.entity.create_entity_task import create_my_app_name_entity
from fastapp_template._zrb.group import (
    app_create_migration_group,
    app_migrate_group,
    app_run_group,
)
from fastapp_template._zrb.helper import (
    create_migration,
    migrate_module,
    run_microservice,
)
from fastapp_template._zrb.module.create_module_task import create_my_app_name_module
from fastapp_template._zrb.venv_task import prepare_venv

from zrb import CmdTask, Env, EnvFile, Task

assert create_my_app_name_entity
assert create_my_app_name_module
assert create_my_app_name_column

# 🚀 Run/Migrate All ===========================================================

run_all = app_run_group.add_task(
    Task(
        name="run-my-app-name",
        description="🟢 Run My App Name as monolith and microservices",
    ),
    alias="all",
)

migrate_all = app_migrate_group.add_task(
    Task(
        name="migrate-my-app-name",
        description="📦 Run My App Name DB migration for monolith and microservices",
    ),
    alias="all",
)

create_all_migration = app_create_migration_group.add_task(
    Task(
        name="create-my-app-name-migration",
        description="📦 Create My App Name DB migration",
    ),
    alias="all",
)

# 🗿 Run/Migrate Monolith =====================================================

run_monolith = app_run_group.add_task(
    CmdTask(
        name="run-monolith-my-app-name",
        description="🗿 Run My App Name as a monolith",
        env=[
            EnvFile(path=os.path.join(APP_DIR, "template.env")),
            Env(name="MY_APP_NAME_MODE", default="monolith"),
        ],
        cwd=APP_DIR,
        cmd=[
            ACTIVATE_VENV_SCRIPT,
            'fastapi dev main.py --port "${MY_APP_NAME_PORT}"',
        ],
        render_cmd=False,
        retries=2,
    ),
    alias="monolith",
)
prepare_venv >> run_monolith >> run_all

migrate_monolith = app_migrate_group.add_task(
    Task(
        name="migrate-monolith-my-app-name",
        description="🗿 Run My App Name DB migration for monolith",
    ),
    alias="monolith",
)
migrate_monolith >> migrate_all

# 🌐 Run/Migrate Microsevices ==================================================

run_microservices = app_run_group.add_task(
    Task(
        name="run-microservices-my-app-name",
        description="🌐 Run My App Name as microservices",
    ),
    alias="microservices",
)
run_microservices >> run_all

migrate_microservices = app_migrate_group.add_task(
    Task(
        name="migrate-microservices-my-app-name",
        description="🌐 Run My App Name DB migration for microservices",
    ),
    alias="microservices",
)
migrate_microservices >> migrate_all

# 📡 Run/Migrate Gateway =======================================================

run_gateway = app_run_group.add_task(
    run_microservice("gateway", 3001, "gateway"), alias="microservices-gateway"
)
prepare_venv >> run_gateway >> run_microservices

create_gateway_migration = app_create_migration_group.add_task(
    create_migration("gateway", "gateway"), alias="gateway"
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

create_auth_migration = app_create_migration_group.add_task(
    create_migration("auth", "auth"), alias="auth"
)
prepare_venv >> create_auth_migration >> create_all_migration

migrate_monolith_auth = migrate_module("auth", "auth", as_microservices=False)
prepare_venv >> migrate_monolith_auth >> [migrate_monolith, run_monolith]

migrate_microservices_auth = app_migrate_group.add_task(
    migrate_module("auth", "auth", as_microservices=True), alias="microservices-auth"
)
prepare_venv >> migrate_microservices_auth >> [migrate_microservices, run_auth]
