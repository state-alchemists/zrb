import os

from fastapp_template._zrb.config import APP_DIR
from fastapp_template._zrb.group import app_create_group
from fastapp_template._zrb.helper import get_existing_module_names
from fastapp_template._zrb.input import new_module_input

from zrb import AnyContext, Scaffolder, Task, make_task
from zrb.util.string.conversion import to_kebab_case, to_pascal_case, to_snake_case


@make_task(
    name="validate-create-my-app-name-module",
    input=new_module_input,
    retries=0,
)
async def validate_create_my_app_name_module(ctx: AnyContext):
    if ctx.input.module in get_existing_module_names():
        raise ValueError(f"Module already exists: {ctx.input.module}")


scaffold_my_app_name_module = Scaffolder(
    name="scaffold-my-app-name-module",
    input=new_module_input,
    source_path=os.path.join(os.path.dirname(__file__), "module_template"),
    render_source_path=False,
    destination_path=lambda ctx: os.path.join(
        APP_DIR,
        "module",
        to_snake_case(ctx.input.module),
    ),
    transform_content={
        "module_template": "{to_snake_case(ctx.input.module)}",
        "MY_MODULE_NAME": "{to_snake_case(ctx.input.module).upper()}",
    },
    retries=0,
    upstream=validate_create_my_app_name_module,
)


@make_task(
    name="register-my-app-name-module-config",
    input=new_module_input,
    upstream=validate_create_my_app_name_module,
    retries=0,
)
async def register_my_app_name_module_config(ctx: AnyContext):
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
    env_name = f"MY_APP_NAME_{upper_module_name}_BASE_URL"
    # TODO: check before write
    with open(config_file_name, "a") as f:
        f.write(f'{config_name} = os.getenv("{env_name}", "{module_base_url}")\n')


@make_task(
    name="register-my-app-name-module",
    input=new_module_input,
    upstream=validate_create_my_app_name_module,
    retries=0,
)
async def register_my_app_name_module(ctx: AnyContext):
    """Registering module to application's main.py"""
    app_main_file_name = os.path.join(APP_DIR, "main.py")
    module_name = to_snake_case(ctx.input.module)
    import_code = f"from fastapp_template.module.{module_name} import route as {module_name}_route"  # noqa
    assert_code = f"assert {module_name}_route"
    with open(app_main_file_name, "r") as f:
        code = f.read()
    new_code = "\n".join([import_code, code.strip(), assert_code, ""])
    # TODO: check before write
    with open(app_main_file_name, "w") as f:
        f.write(new_code)


@make_task(
    name="register-my-app-name-module-runner",
    input=new_module_input,
    upstream=validate_create_my_app_name_module,
    retries=0,
)
async def register_my_app_name_module_runner(ctx: AnyContext):
    """Registering module to _zrb's main.py"""
    task_main_file_name = os.path.join(APP_DIR, "_zrb", "main.py")
    existing_module_names = get_existing_module_names()
    module_port = 3001 + len(
        [
            module_name
            for module_name in existing_module_names
            if module_name != to_snake_case(ctx.input.module)
        ]
    )
    module_snake_name = to_snake_case(ctx.input.module)
    module_kebab_name = to_kebab_case(ctx.input.module)
    module_pascal_name = to_pascal_case(ctx.input.module)
    with open(os.path.join(os.path.dirname(__file__), "run_module.template.py")) as f:
        module_runner_code = (
            f.read()
            .replace("my_module", module_snake_name)
            .replace("my-module", module_kebab_name)
            .replace("My Module", module_pascal_name)
            .replace("3000", f"{module_port}")
        )
    with open(task_main_file_name, "r") as f:
        code = f.read()
    new_code = "\n".join([code.strip(), "", module_runner_code, ""])
    # TODO: check before write
    with open(task_main_file_name, "w") as f:
        f.write(new_code)


create_my_app_name_module = app_create_group.add_task(
    Task(
        name="create-my-app-name-module",
        description="🧩 Create new module on My App Name",
        retries=0,
    ),
    alias="module",
)
create_my_app_name_module << [
    scaffold_my_app_name_module,
    register_my_app_name_module,
    register_my_app_name_module_config,
    register_my_app_name_module_runner,
]
