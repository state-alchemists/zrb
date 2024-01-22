from zrb import HTTPChecker

snake_zrb_app_name_checker = HTTPChecker(
    name="check-kebab-zrb-app-name",
    is_https="{{input.snake_zrb_app_name_https}}",
    host="{{input.snake_zrb_app_name_host}}",
    port="{{env.APP_PORT}}",
    url="/",
)

snake_zrb_app_name_container_checker = HTTPChecker(
    name="check-kebab-zrb-app-name",
    is_https="{{input.snake_zrb_app_name_https}}",
    host="{{input.snake_zrb_app_name_host}}",
    port="{{env.HOST_PORT}}",
    url="/",
)
