import os

from zrb.helper.accessories.name import get_random_name
from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

SYSTEM_USER = os.getenv("USER", "incognito")

project_dir_input = StrInput(
    name="project-dir",
    shortcut="d",
    description="Project directory",
    prompt="Project directory",
    default=".",
)

project_name_input = StrInput(
    name="project-name",
    shortcut="n",
    description="Project name",
    prompt="Project name (can be empty)",
    default="",
)

project_author_name_input = StrInput(
    name="project-author-name",
    prompt="Project author name",
    description="Project author name",
    default=SYSTEM_USER,
)

project_author_email_input = StrInput(
    name="project-author-email",
    prompt="Project author email",
    description="Project author email",
    default=f"{SYSTEM_USER}@gmail.com",
)

project_description_input = StrInput(
    name="project-description",
    description="Project description",
    prompt="Project description",
    default="Just another Zrb project",
)

app_name_input = StrInput(
    name="app-name",
    shortcut="a",
    description="App name",
    prompt="App name",
    default="app",
)

app_author_name_input = StrInput(
    name="app-author-name",
    prompt="App author name",
    description="App author name",
    default=SYSTEM_USER,
)

app_author_email_input = StrInput(
    name="app-author-email",
    prompt="App author email",
    description="App author email",
    default=f"{SYSTEM_USER}@gmail.com",
)

app_description_input = StrInput(
    name="app-description",
    description="App description",
    prompt="App description",
    default="Just another app",
)

app_image_default_namespace = os.getenv(
    "PROJECT_IMAGE_DEFAULT_NAMESPACE", "docker.io/" + SYSTEM_USER
)
app_image_name_input = StrInput(
    name="app-image-name",
    description="App image name",
    prompt="App image name",
    default=app_image_default_namespace
    + "/"
    + "{{util.to_kebab_case(input.app_name)}}",  # noqa
)

module_name_input = StrInput(
    name="module-name",
    shortcut="m",
    description="module name",
    prompt="module name",
    default="library",
)

entity_name_input = StrInput(
    name="entity-name",
    shortcut="e",
    description="Singular entity name",
    prompt="Singular entity name",
    default="book",
)

plural_entity_name_input = StrInput(
    name="plural-entity-name",
    description="Plural entity name",
    prompt="Plural entity name",
    default="books",
)

main_column_name_input = StrInput(
    name="column-name",
    shortcut="c",
    description="Main column name",
    prompt="Main column name",
    default="code",
)

column_name_input = StrInput(
    name="column-name",
    shortcut="c",
    description="Column name",
    prompt="Column name",
    default="title",
)

column_type_input = StrInput(
    name="column-type",
    shortcut="t",
    description="Column type",
    prompt="Column type",
    default="str",
)

task_name_input = StrInput(
    name="task-name",
    shortcut="t",
    description="Task name",
    prompt="Task name",
    default=f"run-{get_random_name()}",
)

http_port_input = IntInput(
    name="http-port",
    shortcut="p",
    description="HTTP port",
    prompt="HTTP port",
    default=8080,
)

env_prefix_input = StrInput(
    name="env-prefix",
    description="OS environment prefix",
    prompt="OS environment prefix",
    default='{{util.to_snake_case(util.coalesce(input.app_name, input.task_name, "MY")).upper()}}',  # noqa
)

package_name_input = StrInput(
    name="package-name",
    shortcut="p",
    description="Package name",
    prompt="Package name",
    default=get_random_name(),
)

package_description_input = StrInput(
    name="package-description",
    description="Package description",
    prompt="Package description",
    default="Just another package",
)

package_homepage_input = StrInput(
    name="package-homepage",
    description="Package homepage",
    prompt="Package homepage",
    default="".join(
        [
            "https://github.com/",
            SYSTEM_USER,
            "/{{util.to_kebab_case(input.package_name)}}",
        ]
    ),
)

package_repository_input = StrInput(
    name="package-repository",
    description="Package repository",
    prompt="Package homepage",
    default="".join(
        [
            "https://github.com/",
            SYSTEM_USER,
            "/{{util.to_kebab_case(input.package_name)}}",
        ]
    ),
)

package_documentation_input = StrInput(
    name="package-documentation",
    description="Package documentation",
    prompt="Package homepage",
    default="".join(
        [
            "https://github.com/",
            SYSTEM_USER,
            "/{{util.to_kebab_case(input.package_name)}}",
        ]
    ),
)

package_author_name_input = StrInput(
    name="package-author-name",
    prompt="Package author name",
    description="Package author name",
    default=SYSTEM_USER,
)

package_author_email_input = StrInput(
    name="package-author-email",
    prompt="Package author email",
    description="Package author email",
    default=f"{SYSTEM_USER}@gmail.com",
)
