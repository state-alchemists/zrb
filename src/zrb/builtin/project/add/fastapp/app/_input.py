import os

from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

SYSTEM_USER = os.getenv("USER", "incognito")

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
