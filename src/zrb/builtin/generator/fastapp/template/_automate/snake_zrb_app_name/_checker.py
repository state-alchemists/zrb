from zrb import HTTPChecker, PortChecker

from ._helper import should_start_local_microservices

rabbitmq_management_checker = HTTPChecker(
    name="check-rabbitmq-management",
    port='{{env.get("RABBITMQ_MANAGEMENT_HOST_PORT", "15672")}}',
    is_https="{{input.snake_zrb_app_name_https}}",
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "rabbitmq"}}',
)

rabbitmq_checker = PortChecker(
    name="check-rabbitmq",
    port='{{env.get("RABBITMQ_HOST_PORT", "5672")}}',
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "rabbitmq"}}',
)

redpanda_console_checker = HTTPChecker(
    name="check-redpanda-console",
    method="GET",
    port='{{env.get("REDPANDA_CONSOLE_HOST_PORT", "9000")}}',
    is_https="{{input.snake_zrb_app_name_https}}",
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "kafka"}}',
)

kafka_plaintext_checker = PortChecker(
    name="check-kafka-plaintext",
    port='{{env.get("KAFKA_INTERNAL_HOST_PORT", "29092")}}',
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "kafka"}}',
)

kafka_outside_checker = PortChecker(
    name="check-kafka-outside",
    port='{{env.get("KAFKA_EXTERNAL_HOST_PORT", "9092")}}',
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "kafka"}}',
)

pandaproxy_plaintext_checker = PortChecker(
    name="check-pandaproxy-plaintext",
    port='{{env.get("PANDAPROXY_INTERNAL_HOST_PORT", "29092")}}',
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "kafka"}}',
)

pandaproxy_outside_checker = PortChecker(
    name="check-pandaproxy-outside",
    port='{{env.get("PANDAPROXY_EXTERNAL_HOST_PORT", "9092")}}',
    should_execute='{{env.get("APP_BROKER_TYPE", "rabbitmq") == "kafka"}}',
)

app_container_checker = HTTPChecker(
    name="check-kebab-zrb-app-name-container",
    host="{{input.snake_zrb_app_name_host}}",
    url="/readiness",
    port='{{env.get("HOST_PORT", "zrbAppHttpPort")}}',
    is_https="{{input.snake_zrb_app_name_https}}",
)

app_local_checker = HTTPChecker(
    name="check-kebab-zrb-app-name",
    host="{{input.snake_zrb_app_name_host}}",
    url="/readiness",
    port="{{env.APP_PORT}}",
    is_https="{{input.snake_zrb_app_name_https}}",
    should_execute=should_start_local_microservices,
)
