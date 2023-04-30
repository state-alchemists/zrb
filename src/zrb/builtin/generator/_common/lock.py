import os

new_task_lock = os.path.sep.join([
    '{{ os.path.join(input.project_dir, "_automate") }}',
    '{{ util.to_snake_case(input.task_name) }}.py'
])

new_task_app_lock = os.path.sep.join([
    '{{ os.path.join(input.project_dir, "_automate") }}',
    '{{ util.to_snake_case(input.app_name) }}.py'
])
