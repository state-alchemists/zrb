'''A Kubernetes Python Pulumi program to deploy kebab-app-name'''

from _common import MODE, BROKER_TYPE
from app_helper import (
    create_app_monolith_deployment, create_app_monolith_service
)
from helm_postgresql_helper import create_postgresql
from helm_rabbitmq_helper import create_rabbitmq
from helm_redpanda_helper import create_redpanda

import pulumi

postgresql = create_postgresql()
pulumi.export('db', postgresql.resources)

if BROKER_TYPE == 'rabbitmq':
    rabbitmq = create_rabbitmq()
    pulumi.export('broker', rabbitmq.resources)
elif BROKER_TYPE == 'kafka':
    redpanda = create_redpanda()
    pulumi.export('broker', redpanda.resources)


if MODE == 'microservices':
    pass
else:
    deployment = create_app_monolith_deployment()
    pulumi.export('app-deployment-names', [deployment.metadata['name']])
    service = create_app_monolith_service()
    pulumi.export('app-service-names', [service.metadata['name']])
