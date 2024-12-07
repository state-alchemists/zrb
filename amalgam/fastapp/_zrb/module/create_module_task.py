import os

from fastapp._zrb.group import app_create_group
from fastapp._zrb.helper import get_existing_module_names
from fastapp._zrb.input import new_module_input
from fastapp._zrb.config import APP_DIR

from zrb import AnyContext, Scaffolder, Task, make_task
from zrb.util.string.conversion import to_snake_case, to_kebab_case

_DIR = os.path.dirname(__file__)


@make_task(
    name="validate-create-fastapp-module",
    input=new_module_input,
    retries=0,
)
def validate_create_fastapp_module(ctx: AnyContext):
    if ctx.input.module in get_existing_module_names():
        raise ValueError(f"Module already exists: {ctx.input.module}")


scaffold_fastapp_module = Scaffolder(
    name="scaffold-fastapp-module",
    input=new_module_input,
    source_path=os.path.join(_DIR, "module_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "module",
        to_snake_case(ctx.input.module),
    ),
    transform_content={
        "module_template": "{to_snake_case(ctx.input.module)}",
        "MY_MODULE_NAME": "{to_snake_case(ctx.input.module).upper()}",
    },
    retries=0,
    upstream=validate_create_fastapp_module,
)


@make_task(
    name="register-fastapp-module-config",
    input=new_module_input,
    upstream=validate_create_fastapp_module,
    retries=0,
)
def register_fastapp_module_config(ctx: AnyContext):
    """Registering module to config.py"""
    existing_module_names = get_existing_module_names()
    module_port = 3000 + len(
        [
            module_name
            for module_name in existing_module_names
            if module_name != to_snake_case(ctx.input.module)
        ]
    )
    module_base_url = f"http://localhost:{module_port}"
    config_file_name = os.path.join(APP_DIR, "config.py")
    upper_module_name = to_snake_case(ctx.input.module).upper()
    config_name = f"APP_{upper_module_name}_BASE_URL"
    env_name = f"FASTAPP_{upper_module_name}_BASE_URL"
    # TODO: check before write
    with open(config_file_name, "a") as f:
        f.write(f'{config_name} = os.getenv("{env_name}", "{module_base_url}")\n')


@make_task(
    name="register-fastapp-module",
    input=new_module_input,
    upstream=validate_create_fastapp_module,
    retries=0,
)
def register_fastapp_module(ctx: AnyContext):
    """Registering module to application's main.py"""
    app_main_file_name = os.path.join(APP_DIR, "main.py")
    module_name = to_snake_case(ctx.input.module)
    import_code = f"from fastapp.module.{module_name} import route as {module_name}_route"  # noqa
    assert_code = f"assert {module_name}_route"
    with open(app_main_file_name, "r") as f:
        code = f.read()
    new_code = "\n".join([import_code, code.strip(), assert_code, ""])
    # TODO: check before write
    with open(app_main_file_name, "w") as f:
        f.write(new_code)


MODULE_RUNNER_SCRIPT = '''
# 🔐 Run/Migrate My Module ==========================================================

run_my_module = app_run_group.add_task(
    run_microservice("my-module", 3002, "my_module"), alias="microservices-my_module"
)
prepare_venv >> run_my_module >> run_microservices

create_my_module_migration = app_create_migration_group.add_task(
    create_migration("my-module", "my_module"), alias="my_module"
)
prepare_venv >> create_my_module_migration >> create_all_migration

migrate_monolith_my_module = migrate_module("my_module", "my_module", as_microservices=False)
prepare_venv >> migrate_monolith_my_module >> [migrate_monolith, run_monolith]

migrate_microservices_my_module = app_migrate_group.add_task(
    migrate_module("my-module", "my_module", as_microservices=True), alias="microservices-my-module"
)
prepare_venv >> migrate_microservices_my_module >> [migrate_microservices, run_my_module]
'''


@make_task(
    name="register-fastapp-module-runner",
    input=new_module_input,
    upstream=validate_create_fastapp_module,
    retries=0,
)
def register_fastapp_module_runner(ctx: AnyContext):
    """Registering module to _zrb's main.py"""
    task_main_file_name = os.path.join(APP_DIR, "_zrb", "main.py")
    module_name = to_snake_case(ctx.input.module)
    module_title = to_kebab_case(ctx.input.module)
    module_runner_code = MODULE_RUNNER_SCRIPT.replace(
        "my_module", module_name
    ).replace(
        "my-module", module_title
    )
    with open(task_main_file_name, "r") as f:
        code = f.read()
    new_code = "\n".join([code.strip(), "", module_runner_code, ""])
    # TODO: check before write
    with open(task_main_file_name, "w") as f:
        f.write(new_code)


create_module = app_create_group.add_task(
    Task(
        name="create-fastapp-module",
        description="🧩 Create new module on Fastapp",
        retries=0
    ),
    alias="module",
)
create_module << [
    scaffold_fastapp_module,
    register_fastapp_module,
    register_fastapp_module_config,
    register_fastapp_module_runner
]
