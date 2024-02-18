import os

from zrb.builtin.generator.common.task_input import (
    package_author_email_input,
    package_author_name_input,
    package_description_input,
    package_documentation_input,
    package_homepage_input,
    package_repository_input,
    project_dir_input,
)
from zrb.builtin.group import plugin_group
from zrb.config.config import version
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.resource_maker import ResourceMaker
from zrb.task_input.str_input import StrInput

CURRENT_DIR = os.path.dirname(__file__)

plugin_package_name_input = StrInput(
    name="package-name",
    shortcut="p",
    description="Package name",
    prompt="Package name",
    default="{{ input.project_dir }}",
)


###############################################################################
# Task Definitions
###############################################################################

copy_resource = ResourceMaker(
    name="copy-resource",
    inputs=[
        project_dir_input,
        plugin_package_name_input,
        package_description_input,
        package_homepage_input,
        package_repository_input,
        package_documentation_input,
        package_author_name_input,
        package_author_email_input,
    ],
    replacements={
        "zrbPackageName": "{{input.package_name}}",
        "zrbPackageDescription": "{{input.package_description}}",
        "zrbPackageHomepage": "{{input.package_homepage}}",
        "zrbPackageRepository": "{{input.package_repository}}",
        "zrbPackageDocumentation": "{{input.package_documentation}}",
        "zrbPackageAuthorName": "{{input.package_author_name}}",
        "zrbPackageAuthorEmail": "{{input.package_author_email}}",
        "zrbVersion": version,
    },
    template_path=os.path.join(CURRENT_DIR, "template"),
    destination_path="{{ input.project_dir }}",
    excludes=[
        "*/__pycache__",
    ],
)

create = CmdTask(
    name="create",
    description="Create plugin",
    group=plugin_group,
    upstreams=[copy_resource],
    inputs=[project_dir_input],
    cmd=[
        "set -e",
        'cd "{{input.project_dir}}"',
        "if [ ! -d .git ]",
        "then",
        "  echo Initialize project git repository",
        "  git init",
        "fi",
        'echo "Happy coding :)"',
    ],
)
runner.register(create)
