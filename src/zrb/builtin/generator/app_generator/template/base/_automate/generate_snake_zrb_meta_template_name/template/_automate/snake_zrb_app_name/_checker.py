from zrb import PortChecker

snake_zrb_app_name_checker = PortChecker(
    name="check-kebab-zrb-app-name",
    host="{{input.snake_zrb_app_name_host}}",
    port="{{env.APP_PORT}}",
)

snake_zrb_app_name_container_checker = PortChecker(
    name="check-kebab-zrb-app-name",
    host="{{input.snake_zrb_app_name_host}}",
    port="{{env.HOST_PORT}}",
)
