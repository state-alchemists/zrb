import os

from fastapp._zrb.group import app_create_group
from fastapp._zrb.helper import get_existing_module_names
from fastapp._zrb.input import new_module_input

from zrb import AnyContext, Scaffolder, Task, make_task
from zrb.util.string.conversion import to_snake_case

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
        "Module Name": "{ctx.input.module.title()}",
        "Module name": "{ctx.input.module.capitalize()}",
        "module-name": "{to_kebab_case(ctx.input.module)}",
        "module_name": "{to_snake_case(ctx.input.module)}",
        "MODULE_NAME": "{to_snake_case(ctx.input.module).upper()}",
    },
    retries=0,
    upstream=validate_create_fastapp_module,
)


@make_task(
    name="register-fastapp-module-config",
    input=new_module_input,
    upstream=validate_create_fastapp_module,
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
    config_file_name = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.py"
    )
    upper_module_name = to_snake_case(ctx.input.module).upper()
    config_name = f"APP_{upper_module_name}_BASE_URL"
    env_name = f"FASTAPP_{upper_module_name}_BASE_URL"
    with open(config_file_name, "a") as f:
        f.write(f'{config_name} = os.getenv("{env_name}", "{module_base_url}")\n')


@make_task(
    name="register-fastapp-module",
    input=new_module_input,
    upstream=validate_create_fastapp_module,
)
def register_fastapp_module(ctx: AnyContext):
    """Registering module to main.py"""
    main_file_name = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "main.py"
    )
    module_name = to_snake_case(ctx.input.module)
    import_code = f"from fastapp.module.{module_name} import route as {module_name}_route"  # noqa
    assert_code = f"assert {module_name}_route"
    with open(main_file_name, "r") as f:
        code = f.read()
    new_code = "\n".join([import_code, code, assert_code])
    with open(main_file_name, "w") as f:
        f.write(new_code)


create_module = app_create_group.add_task(
    Task(name="create-fastapp-module", description="🧩 Create new module on Fastapp"),
    alias="module",
)
create_module << [
    scaffold_fastapp_module,
    register_fastapp_module,
    register_fastapp_module_config,
]
