from ....task_input.str_input import StrInput
from ....task_input.int_input import IntInput
from ....helper.accessories.name import get_random_name
import os

project_dir_input = StrInput(
    name='project-dir',
    shortcut='d',
    description='Project directory',
    prompt='Project directory',
    default='.',
)

project_name_input = StrInput(
    name='project-name',
    shortcut='n',
    description='Project name',
    prompt='Project name (can be empty)',
    default='',
)

app_name_input = StrInput(
    name='app-name',
    shortcut='a',
    description='App name',
    prompt='App name',
    default='app',
)

app_image_default_namespace = os.getenv('USER', 'library')
app_image_name_input = StrInput(
    name='app-image-name',
    description='App image name',
    prompt='App image name',
    default=f'docker.io/{app_image_default_namespace}/' + '{{util.to_kebab_case(input.app_name)}}',  # noqa
)

module_name_input = StrInput(
    name='module-name',
    shortcut='m',
    description='module name',
    prompt='module name',
    default='library',
)

entity_name_input = StrInput(
    name='entity-name',
    shortcut='e',
    description='Singular entity name',
    prompt='Singular entity name',
    default='book'
)

plural_entity_name_input = StrInput(
    name='plural-entity-name',
    description='Plural entity name',
    prompt='Plural entity name',
    default='books'
)

main_column_name_input = StrInput(
    name='column-name',
    shortcut='c',
    description='Main column name',
    prompt='Main column name',
    default='code'
)

column_name_input = StrInput(
    name='column-name',
    shortcut='c',
    description='Column name',
    prompt='Column name',
    default='title'
)

column_type_input = StrInput(
    name='column-type',
    shortcut='t',
    description='Column type',
    prompt='Column type',
    default='str'
)

task_name_input = StrInput(
    name='task-name',
    shortcut='t',
    description='Task name',
    prompt='Task name',
    default=f'run-{get_random_name()}',
)

http_port_input = IntInput(
    name='http-port',
    shortcut='p',
    description='HTTP port',
    prompt='HTTP port',
    default=8080,
)

env_prefix_input = StrInput(
    name='env-prefix',
    description='OS environment prefix',
    prompt='OS environment prefix',
    default='{{util.to_snake_case(util.coalesce(input.app_name, input.task_name, "MY")).upper()}}',  # noqa
)
