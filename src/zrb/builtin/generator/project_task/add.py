from ....helper.file.copy_tree import copy_tree
from ....helper.codemod.add_assert_module import add_assert_module
from ....helper.codemod.add_import_module import add_import_module
from ....helper.codemod.add_upstream_to_task import add_upstream_to_task

import os

current_dir = os.path.dirname(__file__)


def add_default_project_task(project_dir: str):
    if os.path.exists(os.path.join(project_dir, '_automate', '_common.py')):
        return
    copy_tree(
        src=os.path.join(current_dir, 'template'),
        dst=project_dir
    )
    project_task_module_path = '_automate._project'
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    with open(zrb_init_path, 'r') as f:
        code = f.read()
        import_alias = project_task_module_path.split('.')[-1]
        code = add_import_module(
            code=code,
            module_path=project_task_module_path,
            alias=import_alias
        )
        code = add_assert_module(code, import_alias)
    with open(zrb_init_path, 'w') as f:
        f.write(code)


def register_action(
    project_dir: str,
    base_file_name: str,
    task_name: str,
    upstream_task_file: str,
    upstream_task_var: str
):
    default_project_task_dir = os.path.join(
        project_dir, '_automate', '_project'
    )
    default_project_task_file = os.path.join(
        default_project_task_dir, f'{base_file_name}'
    )
    upstream_task_rel_file_path = os.path.relpath(
        upstream_task_file, project_dir
    )
    upstream_module_parts = upstream_task_rel_file_path.split(os.path.sep)
    upstream_module_parts[-1] = os.path.splitext(upstream_module_parts[-1])[0]
    upstream_module_parts.append(upstream_task_var)
    upstream_module_path = '.'.join(upstream_module_parts)
    with open(default_project_task_file, 'r') as f:
        code = f.read()
        code = add_import_module(
            code=code,
            module_path=upstream_module_path,
            resource=upstream_task_var
        )
        code = add_upstream_to_task(
            code, task_name, upstream_task_var
        )
    with open(default_project_task_file, 'w') as f:
        f.write(code)
