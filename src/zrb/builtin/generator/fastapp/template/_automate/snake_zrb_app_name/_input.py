import os

from zrb import BoolInput, ChoiceInput, StrInput

enable_monitoring_input = BoolInput(
    name="enable-kebab-zrb-app-name-monitoring",
    description='Enable "kebab-zrb-app-name" monitoring',
    prompt='Enable "kebab-zrb-app-name" monitoring?',
    default=False,
)

local_input = BoolInput(
    name="local-kebab-zrb-app-name",
    description='Use "kebab-zrb-app-name" on local machine',
    prompt='Use "kebab-zrb-app-name" on local machine?',
    default=True,
)

run_mode_input = ChoiceInput(
    name="kebab-zrb-app-name-run-mode",
    description='"kebab-zrb-app-name" run mode (monolith/microservices)',
    prompt='Run "kebab-zrb-app-name" as a monolith or microservices?',
    choices=["monolith", "microservices"],
    default="monolith",
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

image_input = StrInput(
    name="kebab-zrb-app-name-image",
    description='Image name of "kebab-zrb-app-name"',
    prompt='Image name of "kebab-zrb-app-name"',
    default="zrb-app-image-name:latest",
)

deploy_mode_input = ChoiceInput(
    name="kebab-zrb-app-name-deploy-mode",
    description='"kebab-zrb-app-name" deploy mode (monolith/microservices)',
    prompt='Deploy "kebab-zrb-app-name" as a monolith or microservices?',
    choices=["monolith", "microservices"],
    default="monolith",
)

pulumi_stack_input = StrInput(
    name="kebab-zrb-app-name-pulumi-stack",
    description='Pulumi stack name for "kebab-zrb-app-name"',
    prompt='Pulumi stack name for "kebab-zrb-app-name"',
    default=os.getenv("ZRB_ENV", "dev"),
)
