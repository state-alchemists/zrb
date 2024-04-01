from _common import (
    NAMESPACE,
    POSTGRESQL_AUTH_PASSWORD,
    POSTGRESQL_AUTH_POSTGRES_PASSWORD,
    POSTGRESQL_AUTH_USERNAME,
    POSTGRESQL_DB,
)
from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts


def create_postgresql() -> Chart:
    postgresql = Chart(
        "postgresql",
        LocalChartOpts(
            path="./helm-charts/postgresql",
            namespace=NAMESPACE,
            values={
                "auth": {
                    "postgresPassword": POSTGRESQL_AUTH_POSTGRES_PASSWORD,
                    "username": POSTGRESQL_AUTH_USERNAME,
                    "password": POSTGRESQL_AUTH_PASSWORD,
                    "database": POSTGRESQL_DB,
                },
                "resources": {
                    "limits": {"cpu": "250m", "memory": "256Mi"},
                    "requests": {"cpu": "250m", "memory": "156Mi"},
                },
            },
            skip_await=True,
        ),
    )
    return postgresql
