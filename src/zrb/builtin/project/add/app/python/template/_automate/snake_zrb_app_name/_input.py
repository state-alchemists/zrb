from zrb import BoolInput, StrInput

local_input = BoolInput(
    name="local-kebab-zrb-app-name",
    description='Use "kebab-zrb-app-name" on local machine',
    prompt='Use "kebab-zrb-app-name" on local machine?',
    default=True,
)

https_input = BoolInput(
    name="kebab-zrb-app-name-https",
    description='Whether "kebab-zrb-app-name" run on HTTPS',
    prompt='Is "kebab-zrb-app-name" run on HTTPS?',
    default=False,
)

host_input = StrInput(
    name="kebab-zrb-app-name-host",
    description='Hostname of "kebab-zrb-app-name"',
    prompt='Hostname of "kebab-zrb-app-name"',
    default="localhost",
)
