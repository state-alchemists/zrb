from ._group import snake_zrb_app_name_container_group
from .microservices import (snake_zrb_app_name_microservices_container_group,
                            start_snake_zrb_app_name_microservices_container)
from .monolith import (snake_zrb_app_name_monolith_container_group,
                       start_snake_zrb_app_name_monolith_container)
from .remove import remove_snake_zrb_app_name_container
from .stop import stop_snake_zrb_app_name_container
from .support import (snake_zrb_app_name_support_container_group,
                      start_snake_zrb_app_name_support_container)

assert snake_zrb_app_name_container_group
assert snake_zrb_app_name_microservices_container_group
assert snake_zrb_app_name_monolith_container_group
assert snake_zrb_app_name_support_container_group
assert start_snake_zrb_app_name_microservices_container
assert start_snake_zrb_app_name_monolith_container
assert start_snake_zrb_app_name_support_container
assert remove_snake_zrb_app_name_container
assert stop_snake_zrb_app_name_container
