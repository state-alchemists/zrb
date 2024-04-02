import os

from zrb import BoolInput, IntInput, StrInput

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

replica_input = IntInput(
    name="kebab-zrb-app-name-replica",
    description='Replica of "kebab-zrb-app-name"',
    prompt='Replica of "kebab-zrb-app-name"',
    default=1,
)

pulumi_stack_input = StrInput(
    name="kebab-zrb-app-name-pulumi-stack",
    description='Pulumi stack name for "kebab-zrb-app-name"',
    prompt='Pulumi stack name for "kebab-zrb-app-name"',
    default=os.getenv("ZRB_ENV", "dev"),
)
