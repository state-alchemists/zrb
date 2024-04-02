import os

from zrb.builtin.project._helper import (
    create_register_module,
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.project._input import project_dir_input
from zrb.builtin.project.add.fastapp._group import project_add_fastapp_group
from zrb.builtin.project.add.fastapp.app._input import (
    app_author_email_input,
    app_author_name_input,
    app_description_input,
    app_image_name_input,
    app_name_input,
    env_prefix_input,
    http_port_input,
)
from zrb.helper.accessories.color import colored
from zrb.helper.typing import Any
from zrb.helper.util import to_kebab_case
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

_CURRENT_DIR = os.path.dirname(__file__)
_snake_app_name_tpl = "{{util.to_snake_case(input.app_name)}}"


@python_task(
    name="validate",
    inputs=[project_dir_input, app_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    app_name = kwargs.get("app_name")
    validate_inexisting_automation(project_dir, app_name)
    source_dir = os.path.join(project_dir, "src", f"{to_kebab_case(app_name)}")
    if os.path.exists(source_dir):
        raise Exception(f"Source already exists: {source_dir}")


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        app_name_input,
        app_description_input,
        app_author_name_input,
        app_author_email_input,
        app_image_name_input,
        http_port_input,
        env_prefix_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbAppName": "{{input.app_name}}",
        "zrbAppDescription": "{{input.app_description}}",
        "zrbAppAuthorName": "{{input.app_author_name}}",
        "zrbAppAuthorEmail": "{{input.app_author_email}}",
        "zrbAppHttpPort": '{{util.coalesce(input.http_port, "3000")}}',
        "ZRB_ENV_PREFIX": '{{util.coalesce(input.env_prefix, "MY").upper()}}',
        "zrb-app-image-name": "{{input.app_image_name}}",
        "zrbAppHttpAuthPort": '{{util.coalesce(input.http_port, "3001") + 1}}',
        "zrbAppHttpLogPort": '{{util.coalesce(input.http_port, "3001") + 2}}',
    },
    template_path=os.path.join(_CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/deployment/venv",
        "*/__pycache__",
        "*/src/kebab-zrb-app-name/.venv",
        "*/src/kebab-zrb-app-name/src/frontend/node_modules",
        "*/src/kebab-zrb-app-name/src/frontend/build",
        "*/src/kebab-zrb-app-name/src/frontend/.svelte-kit",
    ],
    skip_parsing=[
        "*.mp3",
        "*.pdf",
        "*.exe",
        "*.dll",
        "*.bin",
        "*.iso",
        "*.png",
        "*.jpg",
        "*.gif",
        "*.ico",
        "*/monitoring/clickhouse/user_scripts/histogramQuantile",
    ],
)

register_module = create_register_module(
    module_path=f"_automate.{_snake_app_name_tpl}",
    alias=f"_automate_{_snake_app_name_tpl}",
    inputs=[app_name_input],
    upstreams=[copy_resource],
)


@python_task(
    name="app",
    group=project_add_fastapp_group,
    description="Add Fastapp application",
    inputs=[
        project_dir_input,
        app_name_input,
        app_description_input,
        app_author_name_input,
        app_author_email_input,
        app_image_name_input,
        http_port_input,
        env_prefix_input,
    ],
    upstreams=[
        register_module,
    ],
    runner=runner,
)
async def add_fastapp_application(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out(colored("Fastapp application added", color="yellow"))
