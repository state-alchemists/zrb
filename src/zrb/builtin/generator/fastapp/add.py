import os

from zrb.builtin.generator.common.helper import (
    validate_existing_project_dir,
    validate_inexisting_automation,
)
from zrb.builtin.generator.common.task_factory import create_register_module
from zrb.builtin.generator.common.task_input import (
    app_author_email_input,
    app_author_name_input,
    app_description_input,
    app_image_name_input,
    app_name_input,
    env_prefix_input,
    http_port_input,
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
from zrb.helper import util
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.resource_maker import ResourceMaker
from zrb.task.task import Task

CURRENT_DIR = os.path.dirname(__file__)
SNAKE_APP_NAME_TPL = "{{util.to_snake_case(input.app_name)}}"

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
    app_dir = os.path.join(project_dir, "src", f"{util.to_kebab_case(app_name)}")
    if os.path.exists(app_dir):
        raise Exception(f"App directory already exists: {app_dir}")


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
        "zrbAppHttpPort": '{{util.coalesce(input.http_port, "3001")}}',
        "ZRB_ENV_PREFIX": '{{util.coalesce(input.env_prefix, "MY").upper()}}',
        "zrb-app-image-name": "{{input.app_image_name}}",
        "zrbAppHttpAuthPort": '{{util.coalesce(input.http_port, "3001") + 1}}',
        "zrbAppHttpLogPort": '{{util.coalesce(input.http_port, "3001") + 2}}',
    },
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
        "*/deployment/venv",
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

register_test_module = create_register_module(
    module_path=f"_automate.{SNAKE_APP_NAME_TPL}.test",
    alias=f"{SNAKE_APP_NAME_TPL}_test",
    inputs=[app_name_input],
    upstreams=[register_deployment_module],
)

register_load_test_module = create_register_module(
    module_path=f"_automate.{SNAKE_APP_NAME_TPL}.load_test",
    alias=f"{SNAKE_APP_NAME_TPL}_load_test",
    inputs=[app_name_input],
    upstreams=[register_test_module],
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
    name="fastapp",
    group=project_add_group,
    upstreams=[
        register_local_module,
        register_container_module,
        register_image_module,
        register_deployment_module,
        register_test_module,
        register_load_test_module,
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
async def add_fastapp(*args: Any, **kwargs: Any):
    task: Task = kwargs.get("_task")
    task.print_out("Success")
