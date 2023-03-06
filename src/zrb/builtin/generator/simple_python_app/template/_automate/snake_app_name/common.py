from zrb import BoolInput, StrInput, Env


local_snake_app_name_input = BoolInput(
    name='local-kebab-app-name',
    description='Use local "kebab-app-name"',
    prompt='Use local "kebab-app-name"?',
    default=True
)

snake_app_name_https_input = BoolInput(
    name='kebab-app-name-https',
    description='Whether "kebab-app-name" run on HTTPS',
    prompt='Is "kebab-app-name" run on HTTPS?',
    default=False
)

snake_app_name_host_input = StrInput(
    name='kebab-app-name-host',
    description='Hostname of "kebab-app-name"',
    prompt='Hostname of "kebab-app-name"',
    default='localhost'
)

snake_app_name_image_input = StrInput(
    name='kebab-app-name-image',
    description='Image name of "kebab-app-name"',
    prompt='Image name of "kebab-app-name"',
    default='app-image-name:latest'
)

snake_app_name_image_env = Env(
    name='IMAGE',
    os_name='ENV_PREFIX_IMAGE',
    default='{{input.snake_app_name_image}}'
)
