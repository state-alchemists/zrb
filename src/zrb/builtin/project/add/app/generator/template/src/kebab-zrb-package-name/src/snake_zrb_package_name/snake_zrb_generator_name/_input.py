import os

from zrb.helper.util import coalesce, to_kebab_case, to_snake_case
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
    default=lambda m: "/".join(
        [app_image_default_namespace, to_kebab_case(m.get("app_name"))]
    ),
)

http_port_input = IntInput(
    name="http-port",
    shortcut="p",
    description="HTTP port",
    prompt="HTTP port",
    default="zrbGeneratorAppPort",
)

env_prefix_input = StrInput(
    name="env-prefix",
    description="OS environment prefix",
    prompt="OS environment prefix",
    default=lambda m: to_snake_case(
        coalesce(m.get("app_name"), m.get("task_name"), "MY")
    ).upper(),
)
