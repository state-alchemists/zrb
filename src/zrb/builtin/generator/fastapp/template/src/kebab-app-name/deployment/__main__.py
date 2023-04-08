'''A Kubernetes Python Pulumi program to deploy kebab-app-name'''

from app import create_app_monolith_deployment, create_app_monolith_service

import pulumi


deployment = create_app_monolith_deployment()
pulumi.export('app-deployment-names', [deployment.metadata['name']])

service = create_app_monolith_service()
pulumi.export('app-service-names', [service.metadata['name']])
