from ._group import snake_zrb_app_name_group
from .container import (
    remove_snake_zrb_app_name_container,
    snake_zrb_app_name_container_group,
    snake_zrb_app_name_microservices_container_group,
    snake_zrb_app_name_monolith_container_group,
    snake_zrb_app_name_support_container_group,
    start_snake_zrb_app_name_microservices_container,
    start_snake_zrb_app_name_monolith_container,
    start_snake_zrb_app_name_support_container,
    stop_snake_zrb_app_name_container,
)
from .image import (
    build_snake_zrb_app_name_image,
    push_snake_zrb_app_name_image,
    snake_zrb_app_name_image_group,
)
from .microservices import (
    deploy_snake_zrb_app_name_microservices,
    destroy_snake_zrb_app_name_microservices,
    start_snake_zrb_app_name_microservices,
    snake_zrb_app_name_microservices_group
)
from .monolith import (
    deploy_snake_zrb_app_name_monolith,
    destroy_snake_zrb_app_name_monolith,
    start_snake_zrb_app_name_monolith,
    snake_zrb_app_name_monolith_group
)

assert snake_zrb_app_name_group
assert snake_zrb_app_name_microservices_group
assert snake_zrb_app_name_monolith_group
assert snake_zrb_app_name_image_group
assert snake_zrb_app_name_container_group
assert snake_zrb_app_name_microservices_container_group
assert snake_zrb_app_name_monolith_container_group
assert snake_zrb_app_name_support_container_group
assert start_snake_zrb_app_name_microservices
assert deploy_snake_zrb_app_name_microservices
assert destroy_snake_zrb_app_name_microservices
assert start_snake_zrb_app_name_monolith
assert deploy_snake_zrb_app_name_monolith
assert destroy_snake_zrb_app_name_monolith
assert remove_snake_zrb_app_name_container
assert stop_snake_zrb_app_name_container
assert start_snake_zrb_app_name_microservices_container
assert start_snake_zrb_app_name_monolith_container
assert start_snake_zrb_app_name_support_container
assert build_snake_zrb_app_name_image
assert push_snake_zrb_app_name_image
