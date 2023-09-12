'''A Kubernetes Python Pulumi program to deploy kebab-zrb-app-name'''

from pulumi_kubernetes.helm.v3 import Chart, LocalChartOpts
import pulumi
import os

CURRENT_DIR = os.path.dirname(__file__)
NAMESPACE = os.getenv('NAMESPACE', 'default')

image = os.getenv('IMAGE', 'kebab-zrb-app-name:latest')
replica = int(os.getenv('REPLICA', '1'))
app_labels = {'app': 'kebab-zrb-app-name'}

# https://www.pulumi.com/registry/packages/kubernetes/api-docs/helm/v3/chart/#local-chart-directory  # noqa
release = Chart(
    'kebab-zrb-app-name',
    LocalChartOpts(
        path='./helm-charts/kebab-zrb-app-name',
        namespace=NAMESPACE,
        values={
        }
    )
)

pulumi.export('helm-release', release.resources)
