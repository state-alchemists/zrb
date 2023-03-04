from zrb import BoolInput, StrInput


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
