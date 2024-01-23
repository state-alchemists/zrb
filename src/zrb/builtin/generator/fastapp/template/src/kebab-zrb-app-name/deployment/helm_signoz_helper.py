from _common import (
    NAMESPACE,
    SIGNOZ_CLICKHOUSE_NAMESPACE,
    SIGNOZ_CLICKHOUSE_PASSWORD,
    SIGNOZ_CLICKHOUSE_USER,
)
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


def create_signoz() -> Chart:
    signoz = Chart(
        "signoz",
        LocalChartOpts(
            path="./helm-charts/signoz",
            namespace=NAMESPACE,
            values={
                "clickhouse": {
                    "enabled": True,
                    "user": SIGNOZ_CLICKHOUSE_USER,
                    "password": SIGNOZ_CLICKHOUSE_PASSWORD,
                    "namespace": SIGNOZ_CLICKHOUSE_NAMESPACE,
                },
                "resources": {
                    "limits": {"cpu": "250m", "memory": "4Gi"},
                    "requests": {"cpu": "250m", "memory": "200Mi"},
                },
            },
            skip_await=True,
        ),
    )
    return signoz
