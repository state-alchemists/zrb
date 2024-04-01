from _common import (
    NAMESPACE,
    REDPANDA_AUTH_MECHANISM,
    REDPANDA_AUTH_SASL_ENABLED,
    REDPANDA_AUTH_USER_NAME,
    REDPANDA_AUTH_USER_PASSWORD,
)
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


def create_redpanda() -> Chart:
    redpanda = Chart(
        "redpanda",
        LocalChartOpts(
            path="./helm-charts/redpanda",
            namespace=NAMESPACE,
            values={
                "auth": {
                    "sasl": {
                        "enabled": REDPANDA_AUTH_SASL_ENABLED,
                        "mechanism": REDPANDA_AUTH_MECHANISM,
                        "users": [
                            {
                                "name": REDPANDA_AUTH_USER_NAME,
                                "password": REDPANDA_AUTH_USER_PASSWORD,
                                "mechanism": REDPANDA_AUTH_MECHANISM,
                            }
                        ],
                    }
                },
            },
            skip_await=True,
        ),
    )
    return redpanda
