from zrb.helper.accessories.name import get_random_name
from zrb.task_input.int_input import IntInput
from zrb.task_input.str_input import StrInput

package_name_input = StrInput(
    name="package-name",
    description="Package name",
    prompt="Package name",
    default=get_random_name(),
)

generator_name_input = StrInput(
    name="generator-name",
    description="Generator name",
    prompt="Generator name",
    default=get_random_name(),
)

generator_base_image_input = StrInput(
    name="generator-base-image",
    description="Base image",
    prompt="Base image",
    default="python:3.10-slim",
)

generator_app_port_input = IntInput(
    name="generator-app-port",
    description="Default app port",
    prompt="Default app port",
    default="8080",
)
