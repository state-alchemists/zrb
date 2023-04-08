from typing import Mapping
from _common import TEMPLATE_ENV_MAP

import pulumi_kubernetes as k8s
import os

image = os.getenv('IMAGE', 'kebab-app-name:latest')
app_monolith_replica = int(os.getenv('REPLICA', '1'))
app_monolith_labels = {'app': 'kebab-app-name'}
app_monolith_env_map = TEMPLATE_ENV_MAP
app_monolith_port = int(os.getenv(
    'APP_PORT', TEMPLATE_ENV_MAP.get('APP_PORT', '8080')
))


def create_app_monolith_deployment() -> k8s.apps.v1.Deployment:
    return create_app_deployment(
        resource_name='kebab-app-name',
        image=image,
        replica=app_monolith_replica,
        app_labels=app_monolith_labels,
        env_map=app_monolith_env_map,
        app_port=app_monolith_port
    )


def create_app_monolith_service() -> k8s.core.v1.Service:
    return create_app_service(
        resource_name='kebab-app-name',
        app_labels=app_monolith_labels,
        app_port=app_monolith_port,
        service_type='LoadBalancer',
        service_port=80,
        service_port_protocol='TCP'
    )


def create_app_deployment(
    resource_name: str,
    image: str,
    replica: int,
    app_labels: Mapping[str, str],
    env_map: Mapping[str, str],
    app_port: int
) -> k8s.apps.v1.Deployment:
    # Pulumi deployment docs:
    # https://www.pulumi.com/registry/packages/kubernetes/api-docs/apps/v1/deployment/
    deployment = k8s.apps.v1.Deployment(
        resource_name=resource_name,
        spec=k8s.apps.v1.DeploymentSpecArgs(
            selector=k8s.meta.v1.LabelSelectorArgs(match_labels=app_labels),
            replicas=replica,
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(labels=app_labels),
                spec=k8s.core.v1.PodSpecArgs(
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name=resource_name,
                            image=image,
                            env=[
                                k8s.core.v1.EnvVarArgs(
                                    name=env_name,
                                    value=os.getenv(env_name, default_value)
                                )
                                for env_name, default_value in env_map.items()
                            ],
                            ports=[
                                k8s.core.v1.ContainerPortArgs(
                                    container_port=app_port
                                )
                            ],
                            liveness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    port=app_port
                                )
                            ),
                            readiness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    port=app_port
                                )
                            ),
                        )
                    ]
                )
            )
        )
    )
    return deployment


def create_app_service(
    resource_name: str,
    app_labels: Mapping[str, str],
    app_port: int,
    service_type: str = 'LoadBalancer',
    service_port: int = 80,
    service_port_protocol: str = 'TCP',
) -> k8s.core.v1.Service:
    # Pulumi services docs:
    # https://www.pulumi.com/registry/packages/kubernetes/api-docs/core/v1/service/
    service = k8s.core.v1.Service(
        resource_name=resource_name,
        spec=k8s.core.v1.ServiceSpecArgs(
            selector=app_labels,
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=service_port,
                    protocol=service_port_protocol,
                    target_port=app_port,
                )
            ],
            type=service_type,
        )
    )
    return service
