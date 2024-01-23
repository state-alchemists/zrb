import os
from typing import Any

from zrb import IntInput, ResourceMaker, StrInput, Task, python_task, runner
from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.generator.common.task_input import (
    app_image_name_input,
    env_prefix_input,
    project_dir_input,
)
from zrb.builtin.generator.project_task.task_factory import (
    create_add_build_images_upstream,
    create_add_deploy_upstream,
    create_add_destroy_upstream,
    create_add_push_images_upstream,
    create_add_remove_containers_upstream,
    create_add_start_containers_upstream,
    create_add_start_upstream,
    create_add_stop_containers_upstream,
    create_ensure_project_tasks,
)
from zrb.builtin.group import project_add_group

CURRENT_DIR = os.path.dirname(__file__)
SNAKE_APP_NAME_TPL = "{{util.to_snake_case(input.app_name)}}"
KEBAB_APP_NAME_TPL = "{{util.to_kebab_case(app_name)}}"

###############################################################################
# Task Inputs
###############################################################################

app_name_input = StrInput(
    name="app-name",
    shortcut="a",
    description="App name",
    prompt="App name",
    default="zrbMetaTemplateName",
)

app_port_input = IntInput(
    name="app-port",
    shortcut="p",
    description="HTTP port",
    prompt="HTTP port",
    default=zrbMetaDefaultAppPort,
)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="validate",
    inputs=[project_dir_input, app_name_input],
)
async def validate(*args: Any, **kwargs: Any):
    project_dir = kwargs.get("project_dir")
    validate_existing_project_dir(project_dir)
    app_name = kwargs.get("app_name")
    validate_inexisting_automation(project_dir, app_name)
    source_dir = os.path.join(project_dir, "src", f"{KEBAB_APP_NAME_TPL}")
    if os.path.exists(source_dir):
        raise Exception(f"Source already exists: {source_dir}")


copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        app_name_input,
        app_image_name_input,
        app_port_input,
        env_prefix_input,
    ],
    upstreams=[validate],
    replacements={
        "zrbAppName": "{{input.app_name}}",
        "zrbAppPort": '{{util.coalesce(input.app_port, "8080")}}',
        "ZRB_ENV_PREFIX": '{{util.coalesce(input.env_prefix, "MY").upper()}}',
        "zrb-app-image-name": "{{input.app_image_name}}",
    },
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/deployment/venv",
        "*/__pycache__",
    ],
)

register_local_module = create_register_module(
    module_path=f"_automate.{SNAKE_APP_NAME_TPL}.local",
    alias=f"{SNAKE_APP_NAME_TPL}_local",
    inputs=[app_name_input],
    upstreams=[copy_resource],
)

register_container_module = create_register_module(
    module_path=f"_automate.{SNAKE_APP_NAME_TPL}.container",
    alias=f"{SNAKE_APP_NAME_TPL}_container",
    inputs=[app_name_input],
    upstreams=[register_local_module],
)

register_image_module = create_register_module(
    module_path=f"_automate.{SNAKE_APP_NAME_TPL}.image",
    alias=f"{SNAKE_APP_NAME_TPL}_image",
    inputs=[app_name_input],
    upstreams=[register_container_module],
)

register_deployment_module = create_register_module(
    module_path=f"_automate.{SNAKE_APP_NAME_TPL}.deployment",
    alias=f"{SNAKE_APP_NAME_TPL}_deployment",
    inputs=[app_name_input],
    upstreams=[register_image_module],
)

ensure_project_tasks = create_ensure_project_tasks(upstreams=[copy_resource])

add_start_upstream = create_add_start_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.local",
    upstream_task_var=f"start_{SNAKE_APP_NAME_TPL}",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_start_container_upstream = create_add_start_containers_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.container",
    upstream_task_var=f"start_{SNAKE_APP_NAME_TPL}_container",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_stop_container_upstream = create_add_stop_containers_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.container",
    upstream_task_var=f"stop_{SNAKE_APP_NAME_TPL}_container",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_remove_container_upstream = create_add_remove_containers_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.container",
    upstream_task_var=f"remove_{SNAKE_APP_NAME_TPL}_container",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_build_image_upstream = create_add_build_images_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.image",
    upstream_task_var=f"build_{SNAKE_APP_NAME_TPL}_image",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_push_image_upstream = create_add_push_images_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.image",
    upstream_task_var=f"push_{SNAKE_APP_NAME_TPL}_image",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_deploy_upstream = create_add_deploy_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.deployment",
    upstream_task_var=f"deploy_{SNAKE_APP_NAME_TPL}",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)

add_destroy_upstream = create_add_destroy_upstream(
    upstream_module=f"_automate.{SNAKE_APP_NAME_TPL}.deployment",
    upstream_task_var=f"destroy_{SNAKE_APP_NAME_TPL}",
    upstreams=[ensure_project_tasks],
    inputs=[app_name_input],
)


@python_task(
    name="kebab-zrb-meta-template-name",
    group=project_add_group,
    upstreams=[
        register_local_module,
        register_container_module,
        register_image_module,
        register_deployment_module,
        add_start_upstream,
        add_start_container_upstream,
        add_stop_container_upstream,
        add_remove_container_upstream,
        add_build_image_upstream,
        add_push_image_upstream,
        add_deploy_upstream,
        add_destroy_upstream,
    ],
    runner=runner,
)
async def snake_zrb_meta_template_name(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
