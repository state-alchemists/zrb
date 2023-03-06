from zrb import (
    CmdTask, runner
)
from zrb.builtin._group import project_group
from .image import push_snake_app_name_image
import os


current_dir = os.path.dirname(__file__)
resource_dir = os.path.abspath(os.path.join(
    current_dir, '..', '..', 'src', 'kebab-app-name'
))
deployment_dir = os.path.join(resource_dir, 'deployment')

env_prefix = 'DEPLOYMENT_ENV_PREFIX'

deploy_snake_app_name_image = CmdTask(
    name='deploy-kebab-app-name-image',
    description='Deploy human readable app name',
    group=project_group,
    upstreams=[push_snake_app_name_image],
    cwd=deployment_dir,
    cmd=[
        '(pulumi stack select dev || pulumi stack init dev)',
        'pulumi up --skip-preview'
    ]
)
runner.register(deploy_snake_app_name_image)

remove_snake_app_name_deployment = CmdTask(
    name='remove-kebab-app-name-deployment',
    description='Remove human readable app name deployment',
    group=project_group,
    cwd=deployment_dir,
    cmd=[
        '(pulumi stack select dev || pulumi stack init dev)',
        'pulumi destroy --skip-preview'
    ]
)
runner.register(remove_snake_app_name_deployment)
