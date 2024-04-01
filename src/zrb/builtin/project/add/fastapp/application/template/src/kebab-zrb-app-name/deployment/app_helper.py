import os
from typing import List, Mapping

import pulumi_kubernetes as k8s
from _common import (
    MODULES,
    NAMESPACE,
    TEMPLATE_ENV_MAP,
    get_app_gateway_env_map,
    get_app_monolith_env_map,
    get_app_service_env_map,
    to_kebab_case,
    to_snake_case,
)

image = os.getenv("IMAGE", "kebab-zrb-app-name:latest")
app_monolith_replica = int(os.getenv("REPLICA", "1"))
app_monolith_labels = {"app": "kebab-zrb-app-name"}
app_gateway_replica = int(os.getenv("REPLICA_GATEWAY"))
app_gateway_labels = {"app": "kebab-zrb-app-name-gateway"}

app_monolith_env_map = get_app_monolith_env_map(TEMPLATE_ENV_MAP, MODULES)
app_port = int(os.getenv("APP_PORT", app_monolith_env_map.get("APP_PORT", "8080")))
app_gateway_env_map = get_app_gateway_env_map(TEMPLATE_ENV_MAP, MODULES)


def create_app_microservices_deployments() -> List[k8s.apps.v1.Deployment]:
    deployments: List[k8s.apps.v1.Deployment] = []
    deployments.append(
        _create_app_deployment(
            resource_name="kebab-zrb-app-name-gateway",
            image=image,
            replica=app_gateway_replica,
            app_labels=app_gateway_labels,
            env_map=app_gateway_env_map,
            app_port=app_port,
        )
    )
    for module in MODULES:
        kebab_module_name = to_kebab_case(module)
        snake_module_name = to_snake_case(module)
        upper_snake_module_name = snake_module_name.upper()
        app_service_replica = int(
            os.getenv(f"REPLICA_{upper_snake_module_name}_SERVICE", "1")
        )
        app_service_env_map = get_app_service_env_map(TEMPLATE_ENV_MAP, MODULES, module)
        app_service_labels = {"app": f"kebab-zrb-app-name-{kebab_module_name}-service"}
        deployments.append(
            _create_app_deployment(
                resource_name=f"kebab-zrb-app-name-{kebab_module_name}-service",
                app_labels=app_service_labels,
                image=image,
                replica=app_service_replica,
                env_map=app_service_env_map,
                app_port=app_port,
            )
        )
    return deployments


def create_app_microservices_services() -> List[k8s.core.v1.Service]:
    services: List[k8s.core.v1.Service] = []
    services.append(
        _create_app_service(
            resource_name="kebab-zrb-app-name-gateway",
            app_labels=app_gateway_labels,
            app_port=app_port,
            service_type="LoadBalancer",
            service_port=app_port,
            service_port_protocol="TCP",
        )
    )
    return services


def create_app_monolith_deployment() -> k8s.apps.v1.Deployment:
    return _create_app_deployment(
        resource_name="kebab-zrb-app-name",
        image=image,
        replica=app_monolith_replica,
        app_labels=app_monolith_labels,
        env_map=app_monolith_env_map,
        app_port=app_port,
    )


def create_app_monolith_service() -> k8s.core.v1.Service:
    return _create_app_service(
        resource_name="kebab-zrb-app-name",
        app_labels=app_monolith_labels,
        app_port=app_port,
        service_type="LoadBalancer",
        service_port=app_port,
        service_port_protocol="TCP",
    )


def _create_app_deployment(
    resource_name: str,
    image: str,
    replica: int,
    app_labels: Mapping[str, str],
    env_map: Mapping[str, str],
    app_port: int,
) -> k8s.apps.v1.Deployment:
    # Pulumi deployment docs:
    # https://www.pulumi.com/registry/packages/kubernetes/api-docs/apps/v1/deployment/
    deployment = k8s.apps.v1.Deployment(
        resource_name=resource_name,
        spec=k8s.apps.v1.DeploymentSpecArgs(
            selector=k8s.meta.v1.LabelSelectorArgs(match_labels=app_labels),
            replicas=replica,
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels=app_labels, namespace=NAMESPACE
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name=resource_name,
                            image=image,
                            env=[
                                k8s.core.v1.EnvVarArgs(name=env_name, value=env_value)
                                for env_name, env_value in env_map.items()
                            ],
                            ports=[
                                k8s.core.v1.ContainerPortArgs(container_port=app_port)
                            ],
                            liveness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    port=app_port, path="/liveness"
                                )
                            ),
                            readiness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    port=app_port, path="/readiness"
                                )
                            ),
                        )
                    ]
                ),
            ),
        ),
    )
    return deployment


def _create_app_service(
    resource_name: str,
    app_labels: Mapping[str, str],
    app_port: int,
    service_type: str = "LoadBalancer",
    service_port: int = 8080,
    service_port_protocol: str = "TCP",
) -> k8s.core.v1.Service:
    # Pulumi services docs:
    # https://www.pulumi.com/registry/packages/kubernetes/api-docs/core/v1/service/
    service = k8s.core.v1.Service(
        resource_name=resource_name,
        metadata=k8s.meta.v1.ObjectMetaArgs(namespace=NAMESPACE),
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
        ),
    )
    return service
