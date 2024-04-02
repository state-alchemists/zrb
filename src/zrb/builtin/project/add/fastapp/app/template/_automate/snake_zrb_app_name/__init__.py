from ._group import snake_zrb_app_name_group
from .backend import (
    prepare_snake_zrb_app_name_backend,
    snake_zrb_app_name_backend_group,
)
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
from .destroy import destroy_snake_zrb_app_name
from .frontend import (
    build_snake_zrb_app_name_frontend,
    build_snake_zrb_app_name_frontend_once,
    snake_zrb_app_name_frontend_group,
)
from .image import (
    build_snake_zrb_app_name_image,
    push_snake_zrb_app_name_image,
    snake_zrb_app_name_image_group,
)
from .load_test import load_test_snake_zrb_app_name
from .microservices import (
    deploy_snake_zrb_app_name_microservices,
    snake_zrb_app_name_microservices_group,
    start_snake_zrb_app_name_microservices,
)
from .monolith import (
    deploy_snake_zrb_app_name_monolith,
    snake_zrb_app_name_monolith_group,
    start_snake_zrb_app_name_monolith,
)
from .test import test_snake_zrb_app_name

assert snake_zrb_app_name_group
assert snake_zrb_app_name_backend_group
assert snake_zrb_app_name_frontend_group
assert snake_zrb_app_name_microservices_group
assert snake_zrb_app_name_monolith_group
assert snake_zrb_app_name_image_group
assert snake_zrb_app_name_container_group
assert snake_zrb_app_name_microservices_container_group
assert snake_zrb_app_name_monolith_container_group
assert snake_zrb_app_name_support_container_group
assert destroy_snake_zrb_app_name
assert start_snake_zrb_app_name_microservices
assert deploy_snake_zrb_app_name_microservices
assert start_snake_zrb_app_name_monolith
assert deploy_snake_zrb_app_name_monolith
assert remove_snake_zrb_app_name_container
assert stop_snake_zrb_app_name_container
assert start_snake_zrb_app_name_microservices_container
assert start_snake_zrb_app_name_monolith_container
assert start_snake_zrb_app_name_support_container
assert build_snake_zrb_app_name_image
assert push_snake_zrb_app_name_image
assert build_snake_zrb_app_name_frontend_once
assert build_snake_zrb_app_name_frontend
assert prepare_snake_zrb_app_name_backend
assert load_test_snake_zrb_app_name
assert test_snake_zrb_app_name
