"""A Kubernetes Python Pulumi program to deploy kebab-zrb-app-name"""

import os

import pulumi
import pulumi_kubernetes as k8s
from dotenv import dotenv_values

_CURRENT_DIR = os.path.dirname(__file__)
_APP_DIR = os.path.join(os.path.dirname(_CURRENT_DIR), "src")
_TEMPLATE_ENV_FILE_NAME = os.path.join(_APP_DIR, "template.env")

image = os.getenv("IMAGE", "kebab-zrb-app-name:latest")
replica = int(os.getenv("REPLICA", "1"))
app_labels = {"app": "kebab-zrb-app-name"}
env_map = dotenv_values(_TEMPLATE_ENV_FILE_NAME)
app_port = int(os.getenv("APP_PORT", env_map.get("APP_PORT", "8080")))

# Pulumi deployment docs:
# https://www.pulumi.com/registry/packages/kubernetes/api-docs/apps/v1/deployment/
deployment = k8s.apps.v1.Deployment(
    resource_name="kebab-zrb-app-name",
    spec=k8s.apps.v1.DeploymentSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(match_labels=app_labels),
        replicas=replica,
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(labels=app_labels),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[
                    k8s.core.v1.ContainerArgs(
                        name="kebab-zrb-app-name",
                        image=image,
                        env=[
                            k8s.core.v1.EnvVarArgs(
                                name=env_name, value=os.getenv(env_name, default_value)
                            )
                            for env_name, default_value in env_map.items()
                        ],
                        ports=[k8s.core.v1.ContainerPortArgs(container_port=app_port)],
                        liveness_probe=k8s.core.v1.ProbeArgs(
                            http_get=k8s.core.v1.HTTPGetActionArgs(port=app_port)
                        ),
                        readiness_probe=k8s.core.v1.ProbeArgs(
                            http_get=k8s.core.v1.HTTPGetActionArgs(port=app_port)
                        ),
                    )
                ]
            ),
        ),
    ),
)

# Pulumi services docs:
# https://www.pulumi.com/registry/packages/kubernetes/api-docs/core/v1/service/
service = k8s.core.v1.Service(
    resource_name="kebab-zrb-app-name",
    spec=k8s.core.v1.ServiceSpecArgs(
        selector=app_labels,
        ports=[
            k8s.core.v1.ServicePortArgs(
                port=app_port,
                protocol="TCP",
                target_port=app_port,
            )
        ],
        type="LoadBalancer",
    ),
)

pulumi.export("deployment-name", deployment.metadata["name"])
pulumi.export("service-name", service.metadata["name"])
