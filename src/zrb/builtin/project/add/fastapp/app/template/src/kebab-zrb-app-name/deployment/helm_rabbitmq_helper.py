from _common import NAMESPACE, RABBITMQ_AUTH_PASSWORD, RABBITMQ_AUTH_USERNAME
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


def create_rabbitmq() -> Chart:
    rabbitmq = Chart(
        "rabbitmq",
        LocalChartOpts(
            path="./helm-charts/rabbitmq",
            namespace=NAMESPACE,
            values={
                "auth": {
                    "username": RABBITMQ_AUTH_USERNAME,
                    "password": RABBITMQ_AUTH_PASSWORD,
                },
                "resources": {
                    "limits": {"cpu": "1000m", "memory": "2Gi"},
                    "requests": {"cpu": "1000m", "memory": "1Gi"},
                },
            },
            skip_await=True,
        ),
    )
    return rabbitmq
