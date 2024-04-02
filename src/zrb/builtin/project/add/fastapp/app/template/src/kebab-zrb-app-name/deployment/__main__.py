"""A Kubernetes Python Pulumi program to deploy kebab-zrb-app-name"""

import pulumi
from _common import BROKER_TYPE, ENABLE_MONITORING, MODE
from app_helper import (
    create_app_microservices_deployments,
    create_app_microservices_services,
    create_app_monolith_deployment,
    create_app_monolith_service,
)
from helm_postgresql_helper import create_postgresql
from helm_rabbitmq_helper import create_rabbitmq
from helm_redpanda_helper import create_redpanda
from helm_signoz_helper import create_signoz

postgresql = create_postgresql()
pulumi.export("db", postgresql.resources)

if BROKER_TYPE == "rabbitmq":
    rabbitmq = create_rabbitmq()
    pulumi.export("broker", rabbitmq.resources)
elif BROKER_TYPE == "kafka":
    redpanda = create_redpanda()
    pulumi.export("broker", redpanda.resources)

if ENABLE_MONITORING:
    signoz = create_signoz()
    pulumi.export("signoz", signoz.resources)

if MODE == "microservices":
    deployments = create_app_microservices_deployments()
    pulumi.export(
        "app-deployment-names",
        [deployment.metadata["name"] for deployment in deployments],
    )
    services = create_app_microservices_services()
    pulumi.export(
        "app-service-names", [service.metadata["name"] for service in services]
    )
else:
    deployment = create_app_monolith_deployment()
    pulumi.export("app-deployment-names", [deployment.metadata["name"]])
    service = create_app_monolith_service()
    pulumi.export("app-service-names", [service.metadata["name"]])
